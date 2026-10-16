"""Art from the news sources: pick each slide's photo from the articles we fetched, download it,
check it's a real photo (not a logo or a placeholder), and record where it came from.

Every source image belongs to someone else. Each one carries a credit for the slide and a rights
note for the reviewer; wire and stock photos (Getty, AP, Reuters, AFP, Shutterstock...) are named
explicitly because they need a license before posting."""

import hashlib
import io
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image

from ...core.urls import canonical, host
from ..extract import Article

MIN_W, MIN_H = 700, 400
MAX_BYTES = 15 * 1024 * 1024
MAX_SAVE_W = 1600

_BAD_PATH = re.compile(r"logo|placeholder|default|fallback|brand|icon|avatar|sprite|social[-_]?share|og[-_]?default", re.I)
_AGENCIES = [
    (re.compile(r"getty\s*images|gettyimages|getty", re.I), "Getty Images"),
    (re.compile(r"\bAP\s*Photo\b|\bAssociated Press\b|apimages", re.I), "AP"),
    (re.compile(r"\breuters\b", re.I), "Reuters"),
    (re.compile(r"\bAFP\b", re.I), "AFP"),
    (re.compile(r"shutterstock", re.I), "Shutterstock"),
    (re.compile(r"\bEPA\b|EPA-EFE", re.I), "EPA"),
    (re.compile(r"\bimago\b", re.I), "Imago"),
    (re.compile(r"alamy", re.I), "Alamy"),
]


@dataclass
class SlideImage:
    path: str                 # local file
    source_url: str           # the image URL
    article_url: str          # the page it came from
    outlet: str               # who published the article
    width: int
    height: int
    agency: str = ""          # wire/stock agency detected in the URL or caption, if any
    credit: str = ""          # short credit for the slide, e.g. "Photo: CNBC / Getty Images"
    rights_note: str = ""     # for the reviewer

    def to_dict(self) -> dict:
        return asdict(self)


def detect_agency(*texts: str) -> str:
    blob = " ".join(t for t in texts if t)
    for pattern, name in _AGENCIES:
        if pattern.search(blob):
            return name
    return ""


def credit_for(outlet: str, agency: str) -> tuple[str, str]:
    if agency and agency.lower() not in outlet.lower():
        return (f"Photo: {outlet} / {agency}",
                f"{agency} photo published by {outlet}: wire/stock image, license it (or swap) before posting")
    return (f"Photo: {outlet}",
            f"{outlet}'s own image: get permission or swap before posting")


def candidates(articles: list[Article], used: set[str]) -> list[tuple[str, Article]]:
    """Image URLs worth trying, best article first. Skips logos, placeholders, SVGs, and images
    already used on another slide (a site's default og:image shows up on every story)."""
    out, seen = [], set()
    for a in articles:
        url = (a.image_url or "").strip()
        if not url or not url.startswith("http") or url.lower().split("?")[0].endswith(".svg"):
            continue
        key = canonical(url)
        if key in seen or key in used or _BAD_PATH.search(url.split("?")[0]):
            continue
        seen.add(key)
        out.append((url, a))
    return out


def download(http, url: str, referer: str, cache_dir: Path) -> tuple[Path, int, int] | None:
    """Fetch, validate and normalise an image to JPEG. Returns (path, width, height) or None."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / (hashlib.sha1(url.encode("utf-8")).hexdigest()[:16] + ".jpg")
    if out.exists():
        with Image.open(out) as im:
            return out, im.width, im.height
    try:
        r = http.get(url, headers={"Referer": referer, "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"})
        r.raise_for_status()
    except Exception:
        return None
    if len(r.content) > MAX_BYTES or not r.headers.get("content-type", "image/").startswith("image/"):
        return None
    try:
        with Image.open(io.BytesIO(r.content)) as im:
            im.load()
            if im.width < MIN_W or im.height < MIN_H:
                return None
            img = im.convert("RGB")
    except Exception:
        return None
    if img.width > MAX_SAVE_W:
        img = img.resize((MAX_SAVE_W, round(img.height * MAX_SAVE_W / img.width)), Image.LANCZOS)
    img.save(out, "JPEG", quality=90)
    return out, img.width, img.height


def pick_image(http, articles: list[Article], cache_dir: Path, used: set[str],
               outlet_names: dict[str, str] | None = None) -> SlideImage | None:
    for url, art in candidates(articles, used):
        got = download(http, url, art.final_url or art.url, cache_dir)
        if not got:
            continue
        path, w, h = got
        outlet = (outlet_names or {}).get(host(art.final_url or art.url)) or art.sitename or host(art.final_url or art.url)
        agency = detect_agency(url, art.image_credit)
        credit, note = credit_for(outlet, agency)
        used.add(canonical(url))
        return SlideImage(path=str(path), source_url=url, article_url=art.final_url or art.url, outlet=outlet,
                          width=w, height=h, agency=agency, credit=credit, rights_note=note)
    return None
