"""Shapes for the news lane. An Item is one article as one source reported it; a Story is the
event behind one or more Items (the unit we rank, triage and turn into a slide)."""

from dataclasses import asdict, dataclass, field


@dataclass
class Item:
    url: str                      # the link a human can open (may be an aggregator redirect)
    title: str
    outlet_domain: str            # matched outlet domain, or the registrable domain if unlisted
    outlet_name: str
    tier: str                     # "1", "2", "3", "4", "official", "company", "unlisted"
    published_at: str | None      # ISO 8601 UTC, when the source gave one
    summary: str = ""
    source_kind: str = ""         # rss | google | bing
    source_ref: str = ""          # the feed URL or search query that produced it
    canonical_url: str = ""       # tracking-free form used for dedupe
    resolved: bool = True         # False when url is a Google News redirect we haven't decoded
    fetched_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Item":
        return cls(**d)


@dataclass
class Story:
    id: str                       # persistent across runs: "st_<10 hex>"
    title: str                    # representative headline (from the lead item)
    items: list[Item]             # sorted: best tier first, then resolved URLs, then earliest
    first_seen: str
    last_seen: str
    score: float = 0.0
    score_parts: dict = field(default_factory=dict)
    on_ramp_hints: list[str] = field(default_factory=list)   # keyword hits; triage confirms
    triage: dict | None = None                               # Claude's judgment, once run

    @property
    def outlets(self) -> list[str]:
        seen, out = set(), []
        for it in self.items:
            if it.outlet_name not in seen:
                seen.add(it.outlet_name)
                out.append(it.outlet_name)
        return out

    @property
    def lead(self) -> Item:
        return self.items[0]

    @property
    def latest_published(self) -> str | None:
        dates = [i.published_at for i in self.items if i.published_at]
        return max(dates) if dates else None

    @property
    def earliest_published(self) -> str | None:
        dates = [i.published_at for i in self.items if i.published_at]
        return min(dates) if dates else None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Story":
        d = dict(d)
        d["items"] = [Item.from_dict(i) for i in d.get("items", [])]
        return cls(**d)
