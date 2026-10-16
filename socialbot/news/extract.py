"""Fetch an article and pull out what drafting and verification need: the text, the byline and
date, and the page's main image with whatever credit the page exposes. Nothing here is trusted
content; it is evidence for the verifier and raw material for the writer."""

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import trafilatura

MIN_TEXT = 300           # less than this and we assume a paywall or a video page

_META = re.compile(r'<meta\s+[^>]*?(?:property|name)=["\']([^"\']+)["\'][^>]*?content=["\']([^"\']*)["\']', re.I)
_META_REV = re.compile(r'<meta\s+[^>]*?content=["\']([^"\']*)["\'][^>]*?(?:property|name)=["\']([^"\']+)["\']', re.I)
_FIGCAPTION = re.compile(r"<figcaption[^>]*>(.*?)</figcaption>", re.I | re.S)
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class Article:
    url: str
    final_url: str = ""
    title: str = ""
    text: str = ""
    author: str = ""
    published_at: str | None = None
    sitename: str = ""
    image_url: str = ""
    image_credit: str = ""      # og:image:alt / twitter:image:alt / first figcaption, if any
    fetched_at: str = ""
    ok: bool = False
    error: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Article":
        return cls(**d)


def meta_tags(html: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for m in _META.finditer(html):
        tags.setdefault(m.group(1).lower(), m.group(2))
    for m in _META_REV.finditer(html):
        tags.setdefault(m.group(2).lower(), m.group(1))
    return tags


def parse_article(html: str, url: str, now: datetime | None = None) -> Article:
    now = now or datetime.now(timezone.utc)
    art = Article(url=url, final_url=url, fetched_at=now.isoformat(timespec="seconds"))
    tags = meta_tags(html)
    try:
        text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False,
                                   favor_precision=True) or ""
    except Exception as e:  # trafilatura is robust, but a bad page must not kill a draft
        text, art.error = "", f"extract: {type(e).__name__}"
    try:
        md = trafilatura.extract_metadata(html, default_url=url)
    except Exception:
        md = None
    art.title = (getattr(md, "title", None) or tags.get("og:title") or "").strip()
    art.author = (getattr(md, "author", None) or tags.get("author") or "").strip()
    art.sitename = (getattr(md, "sitename", None) or tags.get("og:site_name") or "").strip()
    date = getattr(md, "date", None) or tags.get("article:published_time") or ""
    art.published_at = date[:25] if date else None
    art.image_url = (tags.get("og:image") or tags.get("twitter:image") or getattr(md, "image", None) or "").strip()
    credit = tags.get("og:image:alt") or tags.get("twitter:image:alt") or ""
    if not credit:
        cap = _FIGCAPTION.search(html)
        if cap:
            credit = _TAGS.sub(" ", cap.group(1))
    art.image_credit = re.sub(r"\s+", " ", credit).strip()[:300]
    art.text = re.sub(r"[ \t]+", " ", text).strip()
    if len(art.text) >= MIN_TEXT:
        art.ok = True
    elif not art.error:
        art.error = f"only {len(art.text)} chars of text (paywall, video page, or blocked)"
    return art


def fetch_article(http, url: str, now: datetime | None = None) -> Article:
    try:
        r = http.get(url)
        r.raise_for_status()
    except Exception as e:
        return Article(url=url, final_url=url, ok=False, error=f"fetch: {type(e).__name__}: {str(e)[:120]}",
                       fetched_at=(now or datetime.now(timezone.utc)).isoformat(timespec="seconds"))
    art = parse_article(r.text, url, now)
    art.final_url = str(r.url)
    return art
