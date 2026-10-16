"""The news lane, step by step. Each function is small enough to call from tests or the CLI."""

from datetime import datetime, timedelta, timezone

from ..core.db import DB
from ..core import http as http_mod
from .cluster import cluster
from .models import Item, Story
from .rank import rank
from .sources.feeds import fetch_outlet_feeds, fetch_search_feeds


def window(cfg: dict, now: datetime | None = None, days: int | None = None) -> tuple[datetime, datetime]:
    now = now or datetime.now(timezone.utc)
    return now, now - timedelta(days=days or int(cfg["news"].get("window_days", 7)))


def gather(cfg: dict, now: datetime, since: datetime, use_search: bool = True,
           http=None) -> tuple[list[Item], list[tuple[str, str]]]:
    """Every Item the reputable-outlet sources can see in the window, plus a list of source problems."""
    own = http is None
    http = http or http_mod.client(float(cfg["news"].get("http_timeout_seconds", 20)))
    try:
        items, problems = fetch_outlet_feeds(http, cfg, now, since)
        if use_search:
            more, more_problems = fetch_search_feeds(http, cfg, now, since)
            items += more
            problems += more_problems
    finally:
        if own:
            http.close()
    return items, problems


def build_stories(cfg: dict, items: list[Item], now: datetime, since: datetime, db: DB | None = None) -> list[Story]:
    """Cluster against what we already know (persistent IDs), rank, and remember."""
    existing = db.load_stories(since.isoformat(timespec="seconds")) if db else []
    stories = rank(cluster(items, existing, cfg, now), cfg, now)
    if db:
        db.save_stories(stories)
    return stories
