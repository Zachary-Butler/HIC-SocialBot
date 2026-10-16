"""HTML rendering of roundup slides (1080x1350) and a contact sheet, via headless Chromium.

Matches the approved Canva design ("AI NEWS_9_15_26"): photo across the top ~45%, a torn-paper
edge, a grid-paper panel, a coral-red heavy serif headline, a Times-style body with bolded quotes.
Measurements come from that design (headline #e63946, paper #edebe3, cover #eeeeee, tear at ~43%).

If exported template layers exist in assets/template/ (cover-art.png, cta-photo.jpg), they are
used; otherwise the cover is a collage of the week's images and the CTA uses a neutral panel.
Text auto-fits: the body, then the headline, shrink to a floor; anything still overflowing is
reported, never silently clipped."""

import base64
import html
import mimetypes
import random
import re
from pathlib import Path

SLIDE_W, SLIDE_H = 1080, 1350
TEAR_Y = 585                     # where the paper starts (design: ~43% of the height)
RED, PAPER, COVER_BG, GRID = "#e63946", "#edebe3", "#eeeeee", "#d3dfdc"
_BOLD = re.compile(r"\*\*(.+?)\*\*")

FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Abril+Fatface'
         '&family=Tinos:ital,wght@0,400;0,700;1,400;1,700&display=block" rel="stylesheet">')

CSS = f"""
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{SLIDE_W}px;height:{SLIDE_H}px;overflow:hidden;background:{PAPER};font-family:'Tinos','Times New Roman',serif;color:#141414}}
.slide{{position:relative;width:{SLIDE_W}px;height:{SLIDE_H}px;overflow:hidden;background:{PAPER}}}
.photo{{position:absolute;left:0;top:0;width:{SLIDE_W}px;height:{TEAR_Y + 60}px;background:#2b2b2b center 35%/cover no-repeat}}
.photo.empty{{background:linear-gradient(160deg,#5b5650,#2d2a27)}}
.credit{{position:absolute;right:26px;top:22px;font:600 19px/1 Arial,sans-serif;color:rgba(255,255,255,.92);
  text-shadow:0 1px 4px rgba(0,0,0,.75);letter-spacing:.2px}}
.tear{{position:absolute;left:0;top:{TEAR_Y - 40}px}}
.text{{position:absolute;left:64px;right:64px;top:{TEAR_Y + 62}px;bottom:58px;display:flex;flex-direction:column;align-items:center}}
.headline{{font-family:'Abril Fatface','Times New Roman',serif;color:{RED};text-align:center;font-size:72px;line-height:1.04;letter-spacing:.2px}}
.body{{margin-top:30px;text-align:center;font-size:38px;line-height:1.17}}
.body b{{font-weight:700}}
.cover{{background:{COVER_BG}}}
.cover .title{{position:absolute;left:40px;right:40px;top:96px;text-align:center;font-family:'Abril Fatface',serif;color:{RED};font-size:112px;line-height:1.04}}
.cover .kicker{{position:absolute;left:0;right:0;top:362px;text-align:center;font:italic 700 40px/1 'Tinos',serif}}
.cover .art{{position:absolute;left:90px;right:90px;top:450px;height:840px}}
.cover .art img.full{{width:100%;height:100%;object-fit:contain}}
.card{{position:absolute;background:#fff;padding:12px 12px 40px;box-shadow:0 10px 24px rgba(0,0,0,.28)}}
.card div{{width:100%;height:100%;background:center/cover no-repeat}}
.cta .body{{font-weight:700}}
.cta .url{{margin-top:34px;font-family:'Abril Fatface',serif;color:{RED};font-size:62px;text-align:center}}
.cta .foot{{margin-top:12px;font:700 26px/1 'Tinos',serif;letter-spacing:3px;text-align:center}}
"""

FIT_JS = """
() => {
  const box = document.querySelector('.text');
  if (!box) return {overflow: false};
  const h = box.querySelector('.headline'), b = box.querySelector('.body');
  const fits = () => box.scrollHeight <= box.clientHeight + 1;
  let bs = parseFloat(getComputedStyle(b).fontSize), hs = parseFloat(getComputedStyle(h).fontSize);
  while (!fits() && bs > 31) { bs -= 1; b.style.fontSize = bs + 'px'; }
  while (!fits() && hs > 58) { hs -= 2; h.style.fontSize = hs + 'px'; }
  return {overflow: !fits(), body_px: bs, headline_px: hs};
}
"""


def data_uri(path: str | Path) -> str:
    p = Path(path)
    mime = mimetypes.guess_type(p.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(p.read_bytes()).decode("ascii")


def body_to_html(body: str) -> str:
    return _BOLD.sub(r"<b>\1</b>", html.escape(body))


def _doc(inner: str) -> str:
    return f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS}</style></head><body>{inner}</body></html>'


def _ragged(rng: random.Random, y: float, amp: float, step: tuple[int, int]) -> list[tuple[float, float]]:
    pts, x = [], 0.0
    while x < SLIDE_W:
        pts.append((x, y + rng.uniform(-amp, amp)))
        x += rng.uniform(*step)
    pts.append((SLIDE_W, y + rng.uniform(-amp, amp)))
    return pts


def tear_svg(seed: int) -> str:
    """Torn paper: a white fibrous rim with a soft shadow, then the grid paper just below it."""
    rng = random.Random(seed)
    h = SLIDE_H - TEAR_Y + 40
    rim = _ragged(rng, 34, 14, (14, 38))
    paper = [(x, y + rng.uniform(5, 13)) for x, y in rim]
    def poly(top):
        return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in top) + f" L{SLIDE_W},{h} L0,{h} Z"
    return (f'<svg class="tear" width="{SLIDE_W}" height="{h}" viewBox="0 0 {SLIDE_W} {h}" xmlns="http://www.w3.org/2000/svg">'
            f'<defs><filter id="sh" x="-5%" y="-20%" width="110%" height="140%">'
            f'<feDropShadow dx="0" dy="-4" stdDeviation="7" flood-color="#000" flood-opacity=".35"/></filter>'
            f'<filter id="fiber"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" seed="{seed % 97}"/>'
            f'<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 -1.4 1.1"/>'
            f'<feComposite in2="SourceGraphic" operator="in"/></filter>'
            f'<pattern id="grid" width="34" height="34" patternUnits="userSpaceOnUse">'
            f'<path d="M34 0H0V34" fill="none" stroke="{GRID}" stroke-width="2"/></pattern></defs>'
            f'<path d="{poly(rim)}" fill="#fbfaf7" filter="url(#sh)"/>'
            f'<path d="{poly(rim)}" fill="#fbfaf7" filter="url(#fiber)" opacity=".55"/>'
            f'<path d="{poly(paper)}" fill="{PAPER}"/>'
            f'<path d="{poly(paper)}" fill="url(#grid)"/></svg>')


def story_slide_html(headline: str, body: str, image_path: str | None, credit: str = "", seed: int = 1) -> str:
    if image_path:
        photo = f'<div class="photo" style="background-image:url({data_uri(image_path)})"></div>'
        cred = f'<div class="credit">{html.escape(credit)}</div>' if credit else ""
    else:
        photo, cred = '<div class="photo empty"></div>', ""
    return _doc(f'<div class="slide">{photo}{cred}{tear_svg(seed)}'
                f'<div class="text"><div class="headline">{html.escape(headline)}</div>'
                f'<div class="body">{body_to_html(body)}</div></div></div>')


def _collage(image_paths: list[str]) -> str:
    """Cover art fallback: the week's photos as tilted snapshot cards."""
    slots = [(40, 30, 380, 300, -7), (470, 0, 400, 310, 6), (0, 330, 400, 300, 5),
             (430, 300, 440, 330, -4), (80, 560, 380, 280, -3), (480, 580, 400, 280, 7)]
    cards = []
    for (x, y, w, h, rot), path in zip(slots, image_paths):
        cards.append(f'<div class="card" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;transform:rotate({rot}deg)">'
                     f'<div style="background-image:url({data_uri(path)})"></div></div>')
    return "".join(cards)


def cover_slide_html(title: str, kicker: str, cover_art: str | None, week_images: list[str]) -> str:
    art = (f'<img class="full" src="{data_uri(cover_art)}">' if cover_art else _collage(week_images))
    return _doc(f'<div class="slide cover"><div class="title">{html.escape(title)}</div>'
                f'<div class="kicker">{html.escape(kicker)}</div><div class="art">{art}</div></div>')


def cta_slide_html(headline: str, body: str, url_text: str, footer: str, photo: str | None = None, seed: int = 99) -> str:
    bg = (f'<div class="photo" style="background-image:url({data_uri(photo)})"></div>' if photo
          else '<div class="photo empty"></div>')
    return _doc(f'<div class="slide cta">{bg}{tear_svg(seed)}<div class="text">'
                f'<div class="headline">{html.escape(headline)}</div><div class="body">{body_to_html(body)}</div>'
                f'<div class="url">{html.escape(url_text)}</div><div class="foot">{html.escape(footer)}</div></div></div>')


def contact_sheet_html(png_paths: list[Path], title: str, captions: list[str] | None = None) -> str:
    captions = captions or [str(i + 1) for i in range(len(png_paths))]
    cells = "".join(f'<figure><img src="{data_uri(p)}"><figcaption>{html.escape(c)}</figcaption></figure>'
                    for p, c in zip(png_paths, captions))
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>'
            f'body{{margin:0;padding:24px;background:#1e1e1e;color:#eee;font-family:Arial,sans-serif}}'
            f'h1{{font-size:22px;margin:0 0 18px}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:18px}}'
            f'figure{{margin:0}} img{{width:100%;display:block;border-radius:6px}} figcaption{{font-size:14px;color:#bbb;margin-top:6px}}'
            f'</style></head><body><h1>{html.escape(title)}</h1><div class="grid">{cells}</div></body></html>')


def render_pages(pages: list[tuple[str, Path]], timeout_ms: int = 45000) -> list[dict]:
    """Render each (html, out_path) to a PNG. Returns per-page fit info:
    {"path", "overflow", "body_px", "headline_px"}. Needs Playwright + Chromium."""
    from playwright.sync_api import sync_playwright
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context(viewport={"width": SLIDE_W, "height": SLIDE_H}, device_scale_factor=1).new_page()
            for html_text, out in pages:
                out.parent.mkdir(parents=True, exist_ok=True)
                page.set_content(html_text, wait_until="networkidle", timeout=timeout_ms)
                page.evaluate("document.fonts.ready.then(() => true)")
                fit = page.evaluate(FIT_JS) or {}
                page.wait_for_timeout(150)
                page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": SLIDE_W, "height": SLIDE_H})
                results.append({"path": str(out), **fit})
        finally:
            browser.close()
    return results


def render_contact_sheet(png_paths: list[Path], out: Path, title: str, captions: list[str] | None = None,
                         width: int = 1800) -> Path:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context(viewport={"width": width, "height": 1200}).new_page()
            page.set_content(contact_sheet_html(png_paths, title, captions), wait_until="load")
            page.wait_for_timeout(200)
            page.screenshot(path=str(out), full_page=True)
        finally:
            browser.close()
    return out
