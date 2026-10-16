"""Google News RSS links are encoded redirects. We only decode the ones we're about to use (the
lead items of the top stories), because each decode is a network round trip to Google."""

from .cluster import sort_items
from .models import Story
from ..core.urls import canonical, is_aggregator, match_outlet, registrable_domain


def decode_google(url: str) -> str | None:
    try:
        from googlenewsdecoder import gnewsdecoder
    except ImportError:
        return None
    try:
        r = gnewsdecoder(url, interval=1)
    except Exception:
        return None
    if isinstance(r, dict) and r.get("status") and r.get("decoded_url"):
        return r["decoded_url"]
    return None


def resolve_story(story: Story, cfg: dict, max_items: int = 2) -> int:
    """Decode up to `max_items` unresolved items (best first). Returns how many were decoded."""
    done = 0
    for it in story.items:
        if done >= max_items:
            break
        if it.resolved or not is_aggregator(it.url):
            continue
        real = decode_google(it.url)
        if not real:
            continue
        it.url, it.canonical_url, it.resolved = real, canonical(real), True
        outlet = match_outlet(real, cfg["outlets"]["by_domain"])
        if outlet:
            it.outlet_domain, it.outlet_name, it.tier = outlet["domain"], outlet["name"], outlet["tier"]
        elif it.outlet_domain in ("", "news.google.com"):
            it.outlet_domain = registrable_domain(real)
        done += 1
    if done:
        story.items = sort_items(story.items, cfg)
    return done


def resolve_leads(stories: list[Story], cfg: dict, limit: int) -> int:
    return sum(resolve_story(st, cfg) for st in stories[:limit])
