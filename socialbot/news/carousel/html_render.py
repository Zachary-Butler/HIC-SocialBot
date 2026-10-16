"""HTML rendering of roundup slides (1080x1350) and a contact sheet, via headless Chromium.

This is the fallback and preview path. The primary path fills the Canva master (canva.py) so the
design stays editable by hand; this renderer approximates that design closely enough to review
copy and layout, and produces real PNGs if Canva is unavailable."""

import html
import re
from pathlib import Path

SLIDE_W, SLIDE_H = 1080, 1350
_BOLD = re.compile(r"\*\*(.+?)\*\*")

FONTS = ('<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@800;900'
         '&family=Lora:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">')

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;overflow:hidden;background:#f2eee5;font-family:'Lora',Georgia,serif;color:#1a1a1a}
.slide{position:relative;width:1080px;height:1350px;overflow:hidden;background:#f2eee5}
.photo{position:absolute;inset:0 0 auto 0;height:760px;background:#cfc7b8 center/cover no-repeat}
.photo.empty{background:linear-gradient(160deg,#d9d2c3,#b9b0a0)}
.photo .brief{position:absolute;left:60px;right:60px;bottom:40px;color:#fff;font-size:26px;line-height:1.3;text-shadow:0 1px 8px rgba(0,0,0,.6);font-style:italic}
.panel{position:absolute;left:0;right:0;bottom:0;height:650px;padding:92px 70px 60px;
  background:#f7f4ec;background-image:linear-gradient(rgba(60,110,200,.12) 1px,transparent 1px),linear-gradient(90deg,rgba(60,110,200,.12) 1px,transparent 1px);background-size:34px 34px;
  clip-path:polygon(0 3%,3% 0,6% 3%,9% 1%,13% 4%,17% 0,21% 3%,25% 1%,29% 4%,33% 0,37% 3%,41% 1%,45% 4%,49% 0,53% 3%,57% 1%,61% 4%,65% 0,69% 3%,73% 1%,77% 4%,81% 0,85% 3%,89% 1%,93% 4%,97% 0,100% 3%,100% 100%,0 100%)}
.headline{font-family:'Playfair Display',Georgia,serif;font-weight:900;color:#d9382b;text-align:center;font-size:62px;line-height:1.02;letter-spacing:-.5px;margin-bottom:34px}
.headline.long{font-size:54px}
.body{text-align:center;font-size:31px;line-height:1.3;color:#161616}
.body.long{font-size:28px}
.body b{font-weight:700}
.cover{display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding-top:150px;text-align:center}
.cover .title{font-family:'Playfair Display',Georgia,serif;font-weight:900;color:#d9382b;font-size:108px;line-height:1.02}
.cover .kicker{font-style:italic;font-size:40px;margin-top:26px}
.cover .art{margin-top:90px;width:760px;height:620px;border:6px solid #9a9388;border-radius:18px;background:repeating-linear-gradient(45deg,#e8e2d5 0 18px,#f2eee5 18px 36px)}
.cta .panel{height:700px}
.cta .url{font-family:'Playfair Display',Georgia,serif;font-weight:900;color:#d9382b;font-size:56px;text-align:center;margin-top:44px}
.cta .foot{text-align:center;font-size:24px;letter-spacing:4px;margin-top:14px;font-family:Arial,sans-serif}
.num{position:absolute;top:28px;right:34px;font-family:Arial,sans-serif;font-size:22px;color:rgba(0,0,0,.45)}
"""


def body_to_html(body: str) -> str:
    return _BOLD.sub(r"<b>\1</b>", html.escape(body))


def story_slide_html(headline: str, body: str, image_url: str | None, illustration_brief: str,
                     index: int, total: int) -> str:
    h_cls = "headline long" if len(headline) > 56 else "headline"
    b_cls = "body long" if len(body.split()) > 70 else "body"
    if image_url:
        photo = f'<div class="photo" style="background-image:url(\'{html.escape(image_url, quote=True)}\')"></div>'
    else:
        photo = f'<div class="photo empty"><div class="brief">Illustration: {html.escape(illustration_brief)}</div></div>'
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS}</style></head><body>'
            f'<div class="slide">{photo}<div class="panel"><div class="{h_cls}">{html.escape(headline)}</div>'
            f'<div class="{b_cls}">{body_to_html(body)}</div></div><div class="num">{index}/{total}</div></div></body></html>')


def cover_slide_html(title: str, kicker: str) -> str:
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS}</style></head><body>'
            f'<div class="slide cover"><div class="title">{html.escape(title)}</div><div class="kicker">{html.escape(kicker)}</div>'
            f'<div class="art"></div></div></body></html>')


def cta_slide_html(headline: str, body: str, url_text: str, footer: str, image_url: str | None = None) -> str:
    photo = (f'<div class="photo" style="background-image:url(\'{html.escape(image_url, quote=True)}\')"></div>'
             if image_url else '<div class="photo empty"></div>')
    return (f'<!doctype html><html><head><meta charset="utf-8">{FONTS}<style>{CSS}</style></head><body>'
            f'<div class="slide cta">{photo}<div class="panel"><div class="headline">{html.escape(headline)}</div>'
            f'<div class="body">{body_to_html(body)}</div><div class="url">{html.escape(url_text)}</div>'
            f'<div class="foot">{html.escape(footer)}</div></div></div></body></html>')


def contact_sheet_html(png_paths: list[Path], title: str) -> str:
    cells = "".join(f'<figure><img src="{p.resolve().as_uri()}"><figcaption>{i + 1}</figcaption></figure>'
                    for i, p in enumerate(png_paths))
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>'
            f'body{{margin:0;padding:24px;background:#222;color:#eee;font-family:Arial,sans-serif}}'
            f'h1{{font-size:20px;margin:0 0 16px}} .grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}}'
            f'figure{{margin:0}} img{{width:100%;display:block;border-radius:6px}} figcaption{{font-size:13px;color:#aaa;margin-top:4px}}'
            f'</style></head><body><h1>{html.escape(title)}</h1><div class="grid">{cells}</div></body></html>')


def render_pages(pages: list[tuple[str, Path]], timeout_ms: int = 30000) -> list[Path]:
    """Render each (html, out_path) to a PNG. Returns the paths written. Needs Playwright + Chromium."""
    from playwright.sync_api import sync_playwright
    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            ctx = browser.new_context(viewport={"width": SLIDE_W, "height": SLIDE_H}, device_scale_factor=1)
            page = ctx.new_page()
            for html_text, out in pages:
                out.parent.mkdir(parents=True, exist_ok=True)
                page.set_content(html_text, wait_until="networkidle", timeout=timeout_ms)
                page.wait_for_timeout(300)
                page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": SLIDE_W, "height": SLIDE_H})
                written.append(out)
        finally:
            browser.close()
    return written


def render_contact_sheet(png_paths: list[Path], out: Path, title: str, width: int = 1800) -> Path:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_context(viewport={"width": width, "height": 1200}).new_page()
            page.set_content(contact_sheet_html(png_paths, title), wait_until="load")
            page.wait_for_timeout(300)
            page.screenshot(path=str(out), full_page=True)
        finally:
            browser.close()
    return out
