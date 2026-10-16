"""Assemble a roundup from drafted slides: the ordered set a human will approve in one action.
Pre-built slides are atoms; the roundup is an arrangement of them, so swaps and reorders cost
nothing. `news preview` renders it to PNGs and a contact sheet for review."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..core.db import DB
from .carousel.html_render import cover_slide_html, cta_slide_html, render_contact_sheet, render_pages, story_slide_html
from .models import Story
from .pipeline import window


@dataclass
class Roundup:
    id: str
    created_at: str
    slides: list[dict]              # ordered SlideDraft dicts (+ "image_url", "image_note")
    alternates: list[dict]          # ready-enough slides not in the default set
    not_ready: list[dict]           # low confidence or warnings; shown, never auto-included
    status: str = "proposed"        # proposed | approved | posted
    renders: dict = field(default_factory=dict)   # paths of PNGs, once rendered

    def to_dict(self) -> dict:
        return asdict(self)


def _slide_image(db: DB, draft: dict) -> tuple[str, str]:
    """Preview image for a slide: the first fetched article image. Rights are NOT yet checked,
    so this is marked as a preview; the media step replaces it with a cleared photo or illustration."""
    for url in draft.get("sources", []):
        from ..core.urls import canonical
        art = db.get_article(canonical(url))
        if art and art.image_url:
            return art.image_url, f"preview only: article image from {art.sitename or url} (rights unchecked)"
    return "", "no image yet"


def assemble(cfg: dict, db: DB, n: int | None = None, now: datetime | None = None) -> Roundup:
    now = now or datetime.now(timezone.utc)
    _, since = window(cfg, now)
    n = n or int(cfg["news"].get("roundup_slides", 5))
    min_conf = int(cfg["news"].get("min_confidence", 60))
    stories: list[Story] = [s for s in db.load_stories(since.isoformat(timespec="seconds"))
                            if s.triage and s.triage.get("draftable")]
    stories.sort(key=lambda s: (-s.triage["newsworthy"], -s.score))
    ready, not_ready = [], []
    for st in stories:
        d = db.latest_draft(st.id, "slide")
        if not d:
            continue
        d = dict(d)
        d["newsworthy"] = st.triage["newsworthy"]
        d["on_ramp"] = st.triage.get("on_ramp")
        d["image_url"], d["image_note"] = _slide_image(db, d)
        (ready if d["confidence"] >= min_conf and not d["warnings"] else not_ready).append(d)
    rid = "rd_" + now.strftime("%Y%m%d")
    return Roundup(id=rid, created_at=now.isoformat(timespec="seconds"),
                   slides=ready[:n], alternates=ready[n:], not_ready=not_ready)


def render(cfg: dict, roundup: Roundup, out_dir: Path) -> Roundup:
    rc = cfg.get("roundup") or {}
    total = len(roundup.slides) + 2
    pages = [(cover_slide_html(rc.get("cover_title", "What Happened in AI This Week"),
                               rc.get("cover_kicker", "& what you can do about it")), out_dir / "slide-01-cover.png")]
    for i, d in enumerate(roundup.slides, 2):
        pages.append((story_slide_html(d["headline"], d["body"], d.get("image_url") or None,
                                       d.get("illustration_brief", ""), i, total), out_dir / f"slide-{i:02d}.png"))
    pages.append((cta_slide_html(rc.get("cta_headline", ""), rc.get("cta_body", ""), rc.get("cta_url_text", ""),
                                 rc.get("cta_footer", ""), rc.get("cta_image_url")), out_dir / f"slide-{total:02d}-cta.png"))
    pngs = render_pages(pages)
    sheet = render_contact_sheet(pngs, out_dir / "contact-sheet.png", f"{roundup.id}: {len(roundup.slides)} stories")
    roundup.renders = {"slides": [str(p) for p in pngs], "contact_sheet": str(sheet)}
    return roundup


def cmd_news_preview(cfg: dict, args) -> int:
    db = DB(cfg["paths"]["data_dir"] / "socialbot.sqlite")
    try:
        r = assemble(cfg, db, n=args.n)
        print(f"{r.id}: {len(r.slides)} slide(s) in the roundup, {len(r.alternates)} alternate(s), {len(r.not_ready)} not ready")
        for i, d in enumerate(r.slides, 1):
            print(f"  {i}. {d['headline']}  (newsworthy {d['newsworthy']}, confidence {d['confidence']})")
            print(f"     image: {d['image_note']}")
        for d in r.alternates:
            print(f"  alt: {d['headline']}  (newsworthy {d['newsworthy']}, confidence {d['confidence']})")
        for d in r.not_ready:
            why = "; ".join(d["warnings"]) or f"confidence {d['confidence']}"
            print(f"  not ready: {d['headline']}  ({why[:120]})")
        if not r.slides:
            print("Nothing ready to render. Run `socialbot news roundup` first.")
            return 1
        if not args.no_render:
            out_dir = cfg["paths"]["data_dir"] / "roundups" / r.id
            render(cfg, r, out_dir)
            print(f"\nRendered {len(r.renders['slides'])} slides to {out_dir}")
            print(f"Contact sheet: {r.renders['contact_sheet']}")
        db.save_roundup(r.id, r.status, r.to_dict())
        return 0
    finally:
        db.close()
