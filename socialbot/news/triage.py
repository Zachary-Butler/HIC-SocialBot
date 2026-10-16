"""Claude's editorial pass over the ranked candidates: merge duplicate events, judge newsworthiness,
pick the on-ramp, flag risks. Then rules in code have the last word on anything that matters:

  1. Not AI news -> dropped from the roundup candidates (kept in the list, marked).
  2. `election` flag -> never drafted. Shown for awareness only.
  3. `deceased_minor` is also added by a keyword safety net, so it can't be missed.
  4. Candidates the model forgot are kept, untriaged, rather than silently lost.
"""

from pathlib import Path

from ..core.config import ROOT
from ..core.llm import LLM
from .models import Story
from .rank import story_text

RISK_FLAGS = ["election", "policymaker", "deceased_minor", "unverified", "off_issue"]
PROMPT = ROOT / "prompts" / "news_triage.md"
BATCH = 40          # candidates per Claude call; keeps answers well under max_tokens


def schema(on_ramps: list[str]) -> dict:
    event = {
        "type": "object",
        "properties": {
            "ids": {"type": "array", "items": {"type": "string"}},
            "headline": {"type": "string"},
            "is_ai_news": {"type": "boolean"},
            "newsworthy": {"type": "integer"},
            "on_ramp": {"type": "string", "enum": on_ramps + ["none"]},
            "why_it_matters": {"type": "string"},
            "risk_flags": {"type": "array", "items": {"type": "string", "enum": RISK_FLAGS}},
            "reason": {"type": "string"},
        },
        "required": ["ids", "headline", "is_ai_news", "newsworthy", "on_ramp", "why_it_matters", "risk_flags", "reason"],
        "additionalProperties": False,
    }
    return {"type": "object", "properties": {"events": {"type": "array", "items": event}},
            "required": ["events"], "additionalProperties": False}


def system_prompt(cfg: dict) -> str:
    ramps = "\n".join(f"- `{name}`: {spec['description']}" for name, spec in cfg["news"]["on_ramps"].items())
    return Path(PROMPT).read_text(encoding="utf-8").replace("{{ON_RAMPS}}", ramps)


def _escape(text: str) -> str:
    return (text or "").replace("</story", "&lt;/story")


def format_candidates(batch: dict[str, Story]) -> str:
    blocks = []
    for cid, st in batch.items():
        outlets = ", ".join(st.outlets[:6]) + (f" +{len(st.outlets) - 6}" if len(st.outlets) > 6 else "")
        when = (st.latest_published or st.first_seen)[:10]
        lines = [f'<story id="{cid}" outlets="{_escape(outlets)}" tier="{st.lead.tier}" published="{when}">',
                 _escape(st.title)]
        summaries = [i.summary for i in st.items if i.summary][:2]
        for s in summaries:
            lines.append(f"  - {_escape(s[:400])}")
        other_titles = [i.title for i in st.items[1:4] if i.title != st.title]
        if other_titles:
            lines.append("  also headlined: " + " / ".join(_escape(t) for t in other_titles))
        lines.append("</story>")
        blocks.append("\n".join(lines))
    return "Triage these candidate stories.\n\n" + "\n\n".join(blocks)


def run_triage(cfg: dict, llm: LLM, stories: list[Story], limit: int | None = None,
               model: str | None = None) -> list[Story]:
    """Returns the full list: triaged candidates first (merged, ordered by newsworthiness), then the rest."""
    candidates = [s for s in stories if s.score_parts.get("relevant", True)][: limit or BATCH]
    if not candidates:
        return stories
    model = model or cfg["llm"]["triage_model"]
    system = system_prompt(cfg)
    on_ramps = list(cfg["news"]["on_ramps"])

    merged: list[Story] = []
    for start in range(0, len(candidates), BATCH):
        batch = {f"S{i + 1}": s for i, s in enumerate(candidates[start:start + BATCH], start)}
        out = llm.json_call("news_triage", model, system, format_candidates(batch), schema(on_ramps))
        merged += _apply(out, batch, cfg)

    merged_ids = {s.id for s in merged}
    rest = [s for s in stories if s.id not in merged_ids and not any(s.id in (m.triage or {}).get("merged_ids", []) for m in merged)]
    merged.sort(key=lambda s: (-(s.triage or {}).get("newsworthy", 0), -s.score))
    return merged + rest


def _apply(out: dict, batch: dict[str, Story], cfg: dict) -> list[Story]:
    used: set[str] = set()
    results: list[Story] = []
    for ev in out.get("events", []):
        members = [batch[cid] for cid in ev.get("ids", []) if cid in batch and cid not in used]
        if not members:
            continue
        used.update(cid for cid in ev["ids"] if cid in batch)
        # The oldest story keeps its ID (and so its "already drafted" memory); others fold into it.
        members.sort(key=lambda s: s.first_seen)
        head, others = members[0], members[1:]
        for o in others:
            seen = {i.canonical_url or i.url for i in head.items}
            head.items += [i for i in o.items if (i.canonical_url or i.url) not in seen]
        flags = sorted(set(f for f in ev.get("risk_flags", []) if f in RISK_FLAGS))
        head.triage = {
            "headline": ev.get("headline", head.title),
            "is_ai_news": bool(ev.get("is_ai_news")),
            "newsworthy": max(0, min(100, int(ev.get("newsworthy", 0)))),
            "on_ramp": ev.get("on_ramp", "none"),
            "why_it_matters": ev.get("why_it_matters", ""),
            "risk_flags": flags,
            "reason": ev.get("reason", ""),
            "merged_ids": [o.id for o in others],
            "flag_notes": [],
        }
        results.append(head)
    for cid, st in batch.items():          # anything the model left out is still shown, never lost
        if cid not in used:
            st.triage = {"headline": st.title, "is_ai_news": True, "newsworthy": 0, "on_ramp": "none",
                         "why_it_matters": "", "risk_flags": [], "reason": "Triage didn't return a judgment for this story.",
                         "merged_ids": [], "flag_notes": ["not judged by triage"]}
            results.append(st)
    add_keyword_flags(results, cfg)
    apply_rules(results)
    return results


def add_keyword_flags(stories: list[Story], cfg: dict) -> None:
    """Safety net for the hard constraints: add a risk flag when the story's text contains one of
    that flag's phrases from config.yaml > news.risk_keywords, even if triage missed it."""
    for st in stories:
        if not st.triage:
            continue
        text = story_text(st).lower()
        for flag, phrases in (cfg["news"].get("risk_keywords") or {}).items():
            if flag in st.triage["risk_flags"] or flag not in RISK_FLAGS:
                continue
            hit = next((ph for ph in phrases or [] if ph.lower() in text), None)
            if hit:
                st.triage["risk_flags"] = sorted(set(st.triage["risk_flags"]) | {flag})
                st.triage["flag_notes"].append(f"'{flag}' added by keyword safety net (matched \"{hit}\")")


def apply_rules(stories: list[Story]) -> None:
    """Code decides what may be drafted; the model only advises."""
    for st in stories:
        t = st.triage
        if not t:
            continue
        if not t["is_ai_news"] or "off_issue" in t["risk_flags"]:
            t["draftable"], t["blocked_because"] = False, "not AI news for HIC's purposes"
        elif "election" in t["risk_flags"]:
            t["draftable"], t["blocked_because"] = False, "election-adjacent: shown for awareness, never drafted automatically"
        else:
            t["draftable"], t["blocked_because"] = True, ""
