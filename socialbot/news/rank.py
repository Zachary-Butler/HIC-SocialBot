"""Significance ranking for the news lane. No social-traction input, by design: this lane asks
"what mattered this week according to reputable outlets", not "what's popular".

score = w_tier * best outlet tier
      + w_corroboration * how many independent outlets covered it (syndicators excluded; saturating)
      + w_recency * exponential decay on the latest coverage
      + w_on_ramp * whether it touches an HIC on-ramp (keyword pass; triage confirms later)
Stories that don't look AI-related at all are pushed to the bottom (score x 0.15), not dropped,
so they stay visible for tuning the relevance terms.
"""

import math
from datetime import datetime

from ..core.config import tier_weight
from .models import Story
from .relevance import is_ai_related

OFF_TOPIC_FACTOR = 0.15


def story_text(story: Story) -> str:
    return " ".join(f"{i.title} {i.summary}" for i in story.items)


def independent_outlets(story: Story) -> int:
    return len({i.outlet_domain for i in story.items if i.tier != "syndicated"}) or 1


def on_ramp_hits(story: Story, cfg: dict) -> list[str]:
    text = story_text(story).lower()
    hits = []
    for name, spec in (cfg["news"].get("on_ramps") or {}).items():
        if any(str(kw).lower() in text for kw in spec.get("keywords") or []):
            hits.append(name)
    return hits


def score_story(story: Story, cfg: dict, now: datetime) -> tuple[float, dict]:
    rc = cfg["news"]["rank"]
    w = rc["weights"]
    tier = max(tier_weight(cfg, i.tier) for i in story.items)
    n_outlets = independent_outlets(story)
    sat = max(1, int(rc.get("corroboration_saturates_at", 5)))
    corroboration = min(1.0, math.log1p(n_outlets) / math.log1p(sat))
    latest = story.latest_published or story.first_seen
    age_days = max(0.0, (now - datetime.fromisoformat(latest)).total_seconds() / 86400)
    recency = 0.5 ** (age_days / float(rc.get("recency_half_life_days", 3)))
    relevant = is_ai_related(story_text(story), cfg)
    hits = on_ramp_hits(story, cfg) if relevant else []
    on_ramp = 1.0 if hits else 0.0
    total = w["tier"] * tier + w["corroboration"] * corroboration + w["recency"] * recency + w["on_ramp"] * on_ramp
    if not relevant:
        total *= OFF_TOPIC_FACTOR
    parts = {"tier": round(tier, 3), "corroboration": round(corroboration, 3), "recency": round(recency, 3),
             "on_ramp": on_ramp, "relevant": relevant, "outlets": n_outlets, "age_days": round(age_days, 2)}
    return round(total, 4), parts


def rank(stories: list[Story], cfg: dict, now: datetime) -> list[Story]:
    for st in stories:
        st.score, st.score_parts = score_story(st, cfg, now)
        st.on_ramp_hints = on_ramp_hits(st, cfg) if st.score_parts["relevant"] else []
    return sorted(stories, key=lambda s: (-s.score, s.title))
