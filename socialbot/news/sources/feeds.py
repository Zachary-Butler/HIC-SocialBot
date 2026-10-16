"""Reputable-outlet sources for the news lane: the outlets' own RSS/Atom feeds, plus Google News
and Bing News RSS searches that reach outlets without feeds. Parsing is separated from fetching
so tests can run on saved XML with no network."""

import calendar
import html
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser

from ...core.urls import canonical, is_aggregator, match_outlet, registrable_domain, unwrap_bing
from ..models import Item

GOOGLE_URL = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
BING_URL = "https://www.bing.com/news/search?q={q}&format=rss"

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([.,;:!?])")
_TITLE_SEPARATORS = (" - ", " | ", " – ", " — ")


def clean_text(s: str) -> str:
    text = re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub(" ", s or ""))).strip()
    return _SPACE_BEFORE_PUNCT.sub(lambda m: m.group(1), text)   # "minors ." -> "minors."


def _iso(struct_time) -> str | None:
    if not struct_time:
        return None
    return datetime.fromtimestamp(calendar.timegm(struct_time), tz=timezone.utc).isoformat(timespec="seconds")


def strip_outlet_suffix(title: str, outlet_name: str = "") -> str:
    """'Headline - Reuters' -> 'Headline'. Only strips a short trailing segment, so headlines that
    legitimately contain a dash keep it."""
    for sep in _TITLE_SEPARATORS:
        if sep in title:
            head, tail = title.rsplit(sep, 1)
            if (outlet_name and tail.strip().lower() == outlet_name.strip().lower()) or len(tail.split()) <= 4:
                return head.strip()
    return title.strip()


def _outlet_fields(url_or_host: str, outlets: dict, fallback: dict | None = None,
                   fallback_name: str = "") -> tuple[str, str, str]:
    o = match_outlet(url_or_host, outlets["by_domain"]) if url_or_host else None
    o = o or fallback
    if o:
        return o["domain"], o["name"], o["tier"]
    domain = registrable_domain(url_or_host) if url_or_host else ""
    return domain, (fallback_name or domain), "unlisted"


def _entry_published(e) -> str | None:
    return _iso(e.get("published_parsed") or e.get("updated_parsed"))


def parse_outlet_feed(content: bytes, feed_url: str, outlets: dict, outlet: dict,
                      now: datetime, since: datetime) -> list[Item]:
    items = []
    for e in feedparser.parse(content).entries:
        link, title = (e.get("link") or "").strip(), clean_text(e.get("title") or "")
        if not link or not title:
            continue
        published = _entry_published(e)
        if published and datetime.fromisoformat(published) < since:
            continue
        domain, name, tier = _outlet_fields(link, outlets, fallback=outlet)
        items.append(Item(url=link, title=title, outlet_domain=domain, outlet_name=name, tier=tier,
                          published_at=published, summary=clean_text(e.get("summary") or "")[:600],
                          source_kind="rss", source_ref=feed_url, canonical_url=canonical(link),
                          fetched_at=now.isoformat(timespec="seconds")))
    return items


def parse_google(content: bytes, query: str, outlets: dict, now: datetime, since: datetime) -> list[Item]:
    """Google News RSS: links are redirects we don't decode up front; the <source> tag names the
    outlet, which is enough to tier and cluster. Lead items get decoded later (resolve.py)."""
    items = []
    for e in feedparser.parse(content).entries:
        link = (e.get("link") or "").strip()
        src = e.get("source") or {}
        src_href, src_title = src.get("href") or "", clean_text(src.get("title") or "")
        title = strip_outlet_suffix(clean_text(e.get("title") or ""), src_title)
        if not link or not title:
            continue
        published = _entry_published(e)
        if published and datetime.fromisoformat(published) < since:
            continue
        domain, name, tier = _outlet_fields(src_href, outlets, fallback_name=src_title)
        items.append(Item(url=link, title=title, outlet_domain=domain or "news.google.com", outlet_name=name,
                          tier=tier, published_at=published, source_kind="google", source_ref=query,
                          canonical_url=canonical(link), resolved=not is_aggregator(link),
                          fetched_at=now.isoformat(timespec="seconds")))
    return items


def parse_bing(content: bytes, query: str, outlets: dict, now: datetime, since: datetime) -> list[Item]:
    """Bing News RSS: links are apiclick redirects that carry the real URL, so these resolve now."""
    items = []
    for e in feedparser.parse(content).entries:
        link = unwrap_bing((e.get("link") or "").strip())
        title = clean_text(e.get("title") or "")
        if not link or not title or is_aggregator(link):
            continue
        published = _entry_published(e)
        if published and datetime.fromisoformat(published) < since:
            continue
        domain, name, tier = _outlet_fields(link, outlets)
        items.append(Item(url=link, title=strip_outlet_suffix(title, name), outlet_domain=domain, outlet_name=name,
                          tier=tier, published_at=published, summary=clean_text(e.get("summary") or "")[:600],
                          source_kind="bing", source_ref=query, canonical_url=canonical(link),
                          fetched_at=now.isoformat(timespec="seconds")))
    return items


def fetch_outlet_feeds(http, cfg: dict, now: datetime, since: datetime) -> tuple[list[Item], list[tuple[str, str]]]:
    items, problems = [], []
    for outlet in cfg["outlets"]["by_domain"].values():
        for feed_url in outlet["feeds"]:
            try:
                r = http.get(feed_url)
                r.raise_for_status()
                got = parse_outlet_feed(r.content, feed_url, cfg["outlets"], outlet, now, since)
                if not got:
                    problems.append((feed_url, "no entries in the window (feed may be dead or empty)"))
                items += got
            except Exception as e:  # one bad feed must not sink the run
                problems.append((feed_url, f"{type(e).__name__}: {str(e)[:140]}"))
    return items, problems


def fetch_search_feeds(http, cfg: dict, now: datetime, since: datetime) -> tuple[list[Item], list[tuple[str, str]]]:
    items, problems = [], []
    search = cfg["news"].get("search") or {}
    days = int(cfg["news"].get("window_days", 7))
    for q in search.get("queries") or []:
        if search.get("google", True):
            url = GOOGLE_URL.format(q=quote_plus(f"{q} when:{days}d"))
            try:
                r = http.get(url)
                r.raise_for_status()
                items += parse_google(r.content, q, cfg["outlets"], now, since)
            except Exception as e:
                problems.append((f"google: {q}", f"{type(e).__name__}: {str(e)[:140]}"))
        if search.get("bing", True):
            url = BING_URL.format(q=quote_plus(q))
            try:
                r = http.get(url)
                r.raise_for_status()
                items += parse_bing(r.content, q, cfg["outlets"], now, since)
            except Exception as e:
                problems.append((f"bing: {q}", f"{type(e).__name__}: {str(e)[:140]}"))
    return items, problems
