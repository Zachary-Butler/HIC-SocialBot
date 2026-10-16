"""Turns Items into Stories: same canonical URL, or near-identical headlines published close
together, mean the same event. Stories carry persistent IDs: a story seen on Monday keeps its ID
when more outlets pick it up on Wednesday, so nothing is drafted twice."""

import hashlib
import re
from datetime import datetime

from rapidfuzz import fuzz

from ..core.config import tier_weight
from .models import Item, Story
from .sources.feeds import strip_outlet_suffix

_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


def norm_title(title: str) -> str:
    t = strip_outlet_suffix(title).lower()
    t = _NON_ALNUM.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def story_id(item: Item) -> str:
    key = f"{item.canonical_url or item.url}|{norm_title(item.title)}"
    return "st_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _days_apart(a: str | None, b: str | None) -> float | None:
    da, db = _dt(a), _dt(b)
    if not da or not db:
        return None
    return abs((da - db).total_seconds()) / 86400


def sort_items(items: list[Item], cfg: dict) -> list[Item]:
    """Best representative first: highest tier, then a real (non-redirect) URL, then earliest."""
    return sorted(items, key=lambda i: (-tier_weight(cfg, i.tier), not i.resolved, i.published_at or "9999"))


def dedupe_items(items: list[Item]) -> list[Item]:
    """One Item per canonical URL. When two sources report the same URL, keep the richer one."""
    best: dict[str, Item] = {}
    for it in items:
        key = it.canonical_url or it.url
        cur = best.get(key)
        if cur is None or (not cur.resolved and it.resolved) or (not cur.published_at and it.published_at) \
                or (len(it.summary) > len(cur.summary) and it.resolved == cur.resolved):
            best[key] = it
    return list(best.values())


class _Cluster:
    def __init__(self, story: Story | None = None):
        self.story = story
        self.items: list[Item] = list(story.items) if story else []
        self.urls = {i.canonical_url or i.url for i in self.items}
        self.titles = [norm_title(i.title) for i in self.items]

    def add(self, it: Item) -> None:
        key = it.canonical_url or it.url
        if key in self.urls:
            return
        self.urls.add(key)
        self.items.append(it)
        self.titles.append(norm_title(it.title))

    def close_in_time(self, it: Item, max_days: float) -> bool:
        gaps = [g for g in (_days_apart(it.published_at, o.published_at) for o in self.items) if g is not None]
        return not gaps or min(gaps) <= max_days

    def similarity(self, title_norm: str) -> float:
        return max((fuzz.token_set_ratio(title_norm, t) for t in self.titles), default=0.0)


def cluster(items: list[Item], existing: list[Story], cfg: dict, now: datetime) -> list[Story]:
    rank_cfg = cfg["news"]["rank"]
    threshold = float(rank_cfg.get("title_similarity", 82))
    max_days = float(rank_cfg.get("cluster_max_days_apart", 4))
    clusters = [_Cluster(s) for s in existing]

    for it in sorted(dedupe_items(items), key=lambda i: i.published_at or "9999"):
        key = it.canonical_url or it.url
        target = next((c for c in clusters if key in c.urls), None)
        if target is None:
            n = norm_title(it.title)
            best, best_score = None, 0.0
            for c in clusters:
                if not c.close_in_time(it, max_days):
                    continue
                s = c.similarity(n)
                if s >= threshold and s > best_score:
                    best, best_score = c, s
            target = best
        if target is None:
            target = _Cluster()
            clusters.append(target)
        target.add(it)

    now_iso = now.isoformat(timespec="seconds")
    stories = []
    for c in clusters:
        if not c.items:
            continue
        ordered = sort_items(c.items, cfg)
        if c.story:
            st = c.story
            st.items, st.title, st.last_seen = ordered, ordered[0].title, now_iso
        else:
            first = min(c.items, key=lambda i: i.published_at or "9999")
            st = Story(id=story_id(first), title=ordered[0].title, items=ordered, first_seen=now_iso, last_seen=now_iso)
        stories.append(st)
    return stories
