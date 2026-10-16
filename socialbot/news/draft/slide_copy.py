"""Turn one story plus its article text into a finished slide (headline + body) in the social
voice, then verify every quote and number against the article text. A failed check gets one
redraft with the misses spelled out; if it still fails, the slide carries a warning for the human."""

from dataclasses import asdict, dataclass, field
from pathlib import Path

from ...core.config import ROOT
from ...core.llm import LLM
from ..extract import Article
from ..models import Story
from .lint import lint
from .verify import VerifyResult, date_variants, verify

PROMPT = ROOT / "prompts" / "slide_copy.md"
VOICE_DIR = ROOT / "socialbot" / "core" / "voice"
MAX_ARTICLE_CHARS = 7000
MAX_HEADLINE = 70
BODY_WORDS = (55, 80)

SCHEMA = {
    "type": "object",
    "properties": {
        "headline": {"type": "string"},
        "body": {"type": "string"},
        "quotes_used": {"type": "array", "items": {"type": "string"}},
        "numbers_used": {"type": "array", "items": {"type": "string"}},
        "people_named": {"type": "array", "items": {"type": "string"}},
        "officials_named": {"type": "array", "items": {"type": "string"}},
        "attribution_notes": {"type": "string"},
        "image_search": {"type": "array", "items": {"type": "string"}},
        "illustration_brief": {"type": "string"},
        "confidence": {"type": "integer"},
    },
    "required": ["headline", "body", "quotes_used", "numbers_used", "people_named", "officials_named",
                 "attribution_notes", "image_search", "illustration_brief", "confidence"],
    "additionalProperties": False,
}


@dataclass
class SlideDraft:
    story_id: str
    headline: str
    body: str
    quotes_used: list[str]
    numbers_used: list[str]
    attribution_notes: str
    image_search: list[str]
    illustration_brief: str
    confidence: int
    sources: list[str]                       # article URLs the writer saw
    verification: dict                       # VerifyResult as a dict
    warnings: list[str] = field(default_factory=list)
    redrafted: bool = False
    model: str = ""
    people_named: list[str] = field(default_factory=list)
    officials_named: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _read(name: str) -> str:
    return (VOICE_DIR / name).read_text(encoding="utf-8")


def cleared_facts() -> str:
    return _read("facts.md")


def system_prompt() -> str:
    return (Path(PROMPT).read_text(encoding="utf-8")
            .replace("{{VOICE}}", _read("social-voice.md"))
            .replace("{{COMPLIANCE}}", _read("rules/compliance.md"))
            .replace("{{EPISTEMICS}}", _read("rules/epistemics.md"))
            .replace("{{FACTS}}", cleared_facts())
            .replace("{{EXEMPLARS}}", _read("exemplars.md")))


def _escape(text: str) -> str:
    return (text or "").replace("</article", "&lt;/article")


def format_story(story: Story, articles: list[Article], feedback: str = "") -> str:
    t = story.triage or {}
    lines = ["Write the slide for this story.", "",
             f"Editor's headline: {t.get('headline') or story.title}",
             f"Why it matters: {t.get('why_it_matters', '')}",
             f"Outlets covering it: {', '.join(story.outlets[:8])}",
             f"Risk flags: {', '.join(t.get('risk_flags', [])) or 'none'}", ""]
    for a in articles:
        when = a.published_at or "date unknown"
        lines.append(f'<article outlet="{_escape(a.sitename)}" url="{a.final_url or a.url}" published="{when}" byline="{_escape(a.author)}">')
        lines.append(_escape(a.title))
        lines.append(_escape(a.text[:MAX_ARTICLE_CHARS]))
        lines.append("</article>")
        lines.append("")
    if feedback:
        lines += ["REDRAFT REQUIRED. " + feedback]
    return "\n".join(lines)


def _format_checks(draft: dict, res: VerifyResult) -> list[str]:
    w = []
    if len(draft["headline"]) > MAX_HEADLINE:
        w.append(f"headline is {len(draft['headline'])} characters (max {MAX_HEADLINE})")
    n = len(draft["body"].split())
    if not BODY_WORDS[0] <= n <= BODY_WORDS[1]:
        w.append(f"body is {n} words (want {BODY_WORDS[0]}-{BODY_WORDS[1]})")
    if res.quotes_missing:
        w.append("quotes not found in sources: " + " | ".join(res.quotes_missing))
    if res.numbers_missing:
        w.append("numbers not found in sources: " + ", ".join(res.numbers_missing))
    return w


def verification_corpus(articles: list[Article]) -> list[str]:
    """Article text plus the ways a draft may write the article's date (the body often says
    "Tuesday" while the actual date lives in the page metadata), plus HIC's cleared facts."""
    return [a.text + "\n" + date_variants(a.published_at) for a in articles if a.text] + [cleared_facts()]


def draft_slide(cfg: dict, llm: LLM, story: Story, articles: list[Article], model: str | None = None) -> SlideDraft:
    model = model or cfg["llm"]["draft_model"]
    effort = cfg["llm"].get("draft_effort") or cfg["llm"].get("effort")
    usable = [a for a in articles if a.ok] or articles
    sources = verification_corpus(usable)
    system = system_prompt()
    flags = (story.triage or {}).get("risk_flags", [])

    def check(out: dict) -> tuple[VerifyResult, list[str]]:
        res = verify(out["body"] + " " + out["headline"], sources)
        return res, _format_checks(out, res) + lint(out["headline"], out["body"], flags,
                                                   out.get("people_named"), out.get("officials_named"))

    out = llm.json_call("slide_copy", model, system, format_story(story, usable), SCHEMA, effort=effort)
    res, warnings = check(out)
    redrafted = False
    if warnings:
        feedback = ("Fix these problems and return the full slide again: " + "; ".join(warnings)
                    + ". Remove or replace anything the sources don't support verbatim.")
        out = llm.json_call("slide_copy", model, system, format_story(story, usable, feedback), SCHEMA, effort=effort)
        res, warnings = check(out)
        redrafted = True

    return SlideDraft(
        story_id=story.id, headline=out["headline"].strip(), body=out["body"].strip(),
        quotes_used=out.get("quotes_used", []), numbers_used=out.get("numbers_used", []),
        attribution_notes=out.get("attribution_notes", ""), image_search=out.get("image_search", [])[:3],
        illustration_brief=out.get("illustration_brief", ""), confidence=int(out.get("confidence", 0)),
        sources=[a.final_url or a.url for a in usable], verification=asdict(res),
        warnings=warnings, redrafted=redrafted, model=model,
        people_named=out.get("people_named", []), officials_named=out.get("officials_named", []))
