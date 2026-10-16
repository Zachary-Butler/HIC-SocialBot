"""Fetch an article and pull out what drafting and verification need: the text, the byline and
date, and the page's main image with whatever credit the page exposes. Nothing here is trusted
content; it is evidence for the verifier and raw material for the writer.

Two fetch paths: a plain HTTP GET with browser headers, and, when that is blocked or returns a
stub, a headless browser (Playwright) that renders the page like a reader would."""

import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import trafilatura

MIN_TEXT = 300           # less than this and we assume a paywall or a video page
BLOCKED_STATUS = ("401", "403", "406", "429", "503")

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
    via: str = ""               # "http" or "browser"

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


def fetch_html(http, url: str) -> tuple[str, str, str]:
    """Plain GET. Returns (html, final_url, error)."""
    try:
        r = http.get(url)
        r.raise_for_status()
        return r.text, str(r.url), ""
    except Exception as e:
        return "", url, f"fetch: {type(e).__name__}: {str(e)[:120]}"


def render_html(url: str, timeout_ms: int = 30000) -> tuple[str, str, str]:
    """Headless Chromium. Used only when the plain fetch is blocked or returns a stub."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "", url, "render: playwright not installed"
    from ..core.http import BROWSER_UA
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                ctx = browser.new_context(user_agent=BROWSER_UA, locale="en-US", viewport={"width": 1280, "height": 2000})
                page = ctx.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                page.wait_for_timeout(1500)          # let late-loading article bodies settle
                return page.content(), page.url, ""
            finally:
                browser.close()
    except Exception as e:
        return "", url, f"render: {type(e).__name__}: {str(e)[:120]}"


def _should_render(art: Article | None, error: str) -> bool:
    if error:
        return any(code in error for code in BLOCKED_STATUS) or "fetch:" in error
    return art is not None and not art.ok


def fetch_article(http, url: str, now: datetime | None = None, allow_render: bool = True) -> Article:
    now = now or datetime.now(timezone.utc)
    html, final_url, error = fetch_html(http, url)
    art = None
    if html:
        art = parse_article(html, url, now)
        art.final_url, art.via = final_url, "http"
    if allow_render and _should_render(art, error):
        html2, final2, err2 = render_html(url)
        if html2:
            art2 = parse_article(html2, url, now)
            art2.final_url, art2.via = final2, "browser"
            if art2.ok or art is None:
                art = art2
        elif art is None:
            error = f"{error}; {err2}"
    if art is None:
        art = Article(url=url, final_url=final_url, ok=False, error=error or "no content",
                      fetched_at=now.isoformat(timespec="seconds"))
    return art
