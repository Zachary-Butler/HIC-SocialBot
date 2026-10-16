"""Is this story about AI at all? A cheap gate that runs before on-ramp keywords count, so a school
story doesn't rank on "children" and a water story doesn't rank on "data center" keywords alone.
Claude triage makes the final call; this just keeps obvious non-AI news out of the top of the list."""

import re
from functools import lru_cache


@lru_cache(maxsize=8)
def _pattern(terms: tuple[str, ...]) -> re.Pattern:
    parts = []
    for t in terms:
        t = str(t).lower().strip()
        if not t:
            continue
        esc = re.escape(t)
        # Whole-word match for plain words (so "ai" never matches "said"); phrase match otherwise.
        parts.append(rf"\b{esc}\b" if re.fullmatch(r"[a-z0-9]+", t) else esc)
    return re.compile("|".join(parts), re.IGNORECASE)


def is_ai_related(text: str, cfg: dict) -> bool:
    terms = tuple(cfg["news"].get("relevance_terms") or [])
    return bool(terms) and bool(_pattern(terms).search(text or ""))
