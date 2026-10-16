"""Assemble a roundup from drafted slides: the ordered set a human will approve in one action.
Pre-built slides are atoms; the roundup is an arrangement of them, so swaps and reorders cost
nothing. `news preview` picks each slide's photo from its source articles, renders PNGs and a
contact sheet for review."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from ..core.config import ROOT
from ..core.db import DB
from ..core import http as http_mod
from ..core.urls import canonical
from .carousel.html_render import cover_slide_html, cta_slide_html, render_contact_sheet, render_pages, story_slide_html
from .draft.lint import lint
from .media.source_image import pick_image
from .models import Story
from .pipeline import window

TEMPLATE_DIR = ROOT / "assets" / "template"


@dataclass
class Roundup:
    id: str
    created_at: str
    slides: list[dict]              # ordered SlideDraft dicts (+ "image": SlideImage dict or None)
    alternates: list[dict]          # ready-enough slides not in the default set
    not_ready: list[dict]           # low confidence or warnings; shown, never auto-included
    status: str = "proposed"        # proposed | approved | posted
    renders: dict = field(default_factory=dict)   # paths of PNGs, once rendered

    def to_dict(self) -> dict:
        return asdict(self)


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
        # Rules can change after a draft is stored; re-run the rule checks so new rules apply retroactively.
        fresh = lint(d["headline"], d["body"], st.triage.get("risk_flags", []),
                     d.get("people_named"), d.get("officials_named"))
        d["warnings"] = list(d["warnings"]) + [w for w in fresh if w not in d["warnings"]]
        (ready if d["confidence"] >= min_conf and not d["warnings"] else not_ready).append(d)
    rid = "rd_" + now.strftime("%Y%m%d-%H%M")
    return Roundup(id=rid, created_at=now.isoformat(timespec="seconds"),
                   slides=ready[:n], alternates=ready[n:], not_ready=not_ready)


def attach_images(cfg: dict, db: DB, roundup: Roundup) -> None:
    """Each slide gets a photo from its own source articles; no photo is used twice."""
    by_host = {d: o["name"] for d, o in cfg["outlets"]["by_domain"].items()}
    cache_dir = cfg["paths"]["data_dir"] / "images"
    used: set[str] = set()
    http = http_mod.browser_client()
    try:
        for d in roundup.slides:
            arts = [a for a in (db.get_article(canonical(u)) for u in d.get("sources", [])) if a]
            img = pick_image(http, arts, cache_dir, used, by_host)
            d["image"] = img.to_dict() if img else None
    finally:
        http.close()


def _template(name: str) -> str | None:
    for ext in (".png", ".jpg", ".jpeg"):
        p = TEMPLATE_DIR / f"{name}{ext}"
        if p.exists():
            return str(p)
    return None


def render(cfg: dict, roundup: Roundup, out_dir: Path) -> Roundup:
    rc = cfg.get("roundup") or {}
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("*.png"):          # a shorter roundup must not leave last run's slides behind
        old.unlink()
    week_images = [d["image"]["path"] for d in roundup.slides if d.get("image")]
    total = len(roundup.slides) + 2
    pages = [(cover_slide_html(rc.get("cover_title", "What Happened in AI This Week"),
                               rc.get("cover_kicker", "& what you can do about it"),
                               _template("cover-art"), week_images), out_dir / "slide-01-cover.png")]
    for i, d in enumerate(roundup.slides, 2):
        img = d.get("image") or {}
        pages.append((story_slide_html(d["headline"], d["body"], img.get("path"), img.get("credit", ""), seed=i),
                      out_dir / f"slide-{i:02d}.png"))
    pages.append((cta_slide_html(rc.get("cta_headline", ""), rc.get("cta_body", ""), rc.get("cta_url_text", ""),
                                 rc.get("cta_footer", ""), _template("cta-photo")), out_dir / f"slide-{total:02d}-cta.png"))
    fits = render_pages(pages)
    for d, fit in zip(roundup.slides, fits[1:-1]):
        if fit.get("overflow"):
            d["warnings"] = list(d["warnings"]) + ["text overflows the slide even at the smallest type size"]
    pngs = [Path(f["path"]) for f in fits]
    captions = ["cover"] + [f"{i}. {d['headline'][:48]}" for i, d in enumerate(roundup.slides, 1)] + ["call to action"]
    sheet = render_contact_sheet(pngs, out_dir / "contact-sheet.png",
                                 f"{roundup.id}: {len(roundup.slides)} stories", captions)
    roundup.renders = {"slides": [str(p) for p in pngs], "contact_sheet": str(sheet), "fit": fits}
    return roundup


def cmd_news_preview(cfg: dict, args) -> int:
    db = DB(cfg["paths"]["data_dir"] / "socialbot.sqlite")
    try:
        r = assemble(cfg, db, n=args.n)
        print(f"{r.id}: {len(r.slides)} slide(s) in the roundup, {len(r.alternates)} alternate(s), {len(r.not_ready)} not ready")
        if not r.slides:
            print("Nothing ready to render. Run `socialbot news roundup` first.")
            return 1
        attach_images(cfg, db, r)
        for i, d in enumerate(r.slides, 1):
            img = d.get("image")
            print(f"  {i}. {d['headline']}  (newsworthy {d['newsworthy']}, confidence {d['confidence']})")
            print(f"     image: {img['credit'] + ' · ' + img['rights_note'] if img else 'none found in the sources'}")
        for d in r.alternates:
            print(f"  alt: {d['headline']}  (newsworthy {d['newsworthy']}, confidence {d['confidence']})")
        for d in r.not_ready:
            why = "; ".join(d["warnings"]) or f"confidence {d['confidence']}"
            print(f"  not ready: {d['headline']}  ({why[:120]})")
        if not args.no_render:
            out_dir = cfg["paths"]["data_dir"] / "roundups" / r.id
            render(cfg, r, out_dir)
            print(f"\nRendered {len(r.renders['slides'])} slides to {out_dir}")
            print(f"Contact sheet: {r.renders['contact_sheet']}")
        db.save_roundup(r.id, r.status, r.to_dict())
        return 0
    finally:
        db.close()
