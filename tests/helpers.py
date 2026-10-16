"""Shared fixtures: the real config with a temp data dir, a fixed clock, and item builders. No network."""

import copy
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from socialbot.core.config import load_config
from socialbot.core.urls import canonical
from socialbot.news.models import Item

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
SINCE = NOW - timedelta(days=7)


def make_config() -> dict:
    cfg = copy.deepcopy(load_config())
    cfg["paths"]["data_dir"] = Path(tempfile.mkdtemp(prefix="socialbot-test-"))
    return cfg


def item(url: str, title: str, outlet: str = "Example", domain: str = "", tier: str = "unlisted",
         hours_old: float = 24, kind: str = "rss", resolved: bool = True, summary: str = "") -> Item:
    from socialbot.core.urls import registrable_domain
    return Item(url=url, title=title, outlet_domain=domain or registrable_domain(url), outlet_name=outlet, tier=tier,
                published_at=(NOW - timedelta(hours=hours_old)).isoformat(timespec="seconds"), summary=summary,
                source_kind=kind, source_ref="test", canonical_url=canonical(url), resolved=resolved,
                fetched_at=NOW.isoformat(timespec="seconds"))
