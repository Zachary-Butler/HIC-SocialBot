"""News-lane commands that need a story from the store: fetch its articles, draft its slide."""

from datetime import datetime, timezone

from ..core.db import DB
from ..core import http as http_mod
from ..core.llm import LLM, LLMError
from .draft.slide_copy import SlideDraft, draft_slide
from .extract import Article, fetch_article
from .models import Story
from .resolve import resolve_story

ARTICLES_PER_STORY = 2


def articles_for(cfg: dict, db: DB, story: Story, http, refresh: bool = False) -> list[Article]:
    """Fetch (or load from cache) the text of the best `ARTICLES_PER_STORY` articles for a story:
    distinct outlets, resolved URLs, syndicators last."""
    resolve_story(story, cfg, max_items=3)
    picked, domains = [], set()
    for it in story.items:
        if not it.resolved or it.outlet_domain in domains or it.tier == "syndicated":
            continue
        key = it.canonical_url or it.url
        art = None if refresh else db.get_article(key)
        if art is None:
            art = fetch_article(http, it.url, datetime.now(timezone.utc))
            db.save_article(key, art)
        domains.add(it.outlet_domain)
        picked.append(art)
        if len([a for a in picked if a.ok]) >= ARTICLES_PER_STORY or len(picked) >= ARTICLES_PER_STORY + 2:
            break
    return picked


def print_draft(d: SlideDraft, articles: list[Article]) -> None:
    print(f"\n{d.headline}  ({len(d.headline)} chars)\n")
    print(d.body)
    print(f"\n  {len(d.body.split())} words · confidence {d.confidence}/100 · model {d.model}"
          + (" · redrafted once" if d.redrafted else ""))
    v = d.verification
    print(f"  verification: {len(v['quotes_found'])} quote(s) and {len(v['numbers_found'])} number(s) found in sources"
          + (f"; MISSING quotes: {v['quotes_missing']}" if v["quotes_missing"] else "")
          + (f"; MISSING numbers: {v['numbers_missing']}" if v["numbers_missing"] else ""))
    for w in d.warnings:
        print(f"  ⚠ {w}")
    print(f"  attribution: {d.attribution_notes}")
    print(f"  image search: {', '.join(d.image_search)}")
    print(f"  illustration: {d.illustration_brief}")
    print("  sources:")
    for a in articles:
        status = "ok" if a.ok else f"NOT USABLE ({a.error})"
        print(f"    - {a.final_url or a.url}  [{status}]" + (f"  image: {a.image_url}" if a.image_url else ""))


def cmd_news_draft(cfg: dict, args) -> int:
    db = DB(cfg["paths"]["data_dir"] / "socialbot.sqlite")
    http = http_mod.client(float(cfg["news"].get("http_timeout_seconds", 20)))
    try:
        story = db.get_story(args.story_id)
        if not story:
            print(f"No story {args.story_id} in the store. Run `socialbot news build` first.")
            return 1
        print(f"{story.title}\n  {', '.join(story.outlets[:6])} · [{story.id}]")
        t = story.triage or {}
        if t and not t.get("draftable", True) and not args.force:
            print(f"  NOT DRAFTABLE: {t.get('blocked_because')} (use --force to draft anyway for review)")
            return 1
        articles = articles_for(cfg, db, story, http, refresh=args.refresh)
        usable = [a for a in articles if a.ok]
        print(f"  {len(usable)}/{len(articles)} article(s) with usable text", flush=True)
        if not usable:
            print("  No article text to draft from; the slide would be headline-only. Stopping.")
            for a in articles:
                print(f"    - {a.url}: {a.error}")
            return 1
        llm = LLM(cfg, reuse=args.reuse_llm)
        try:
            d = draft_slide(cfg, llm, story, articles)
        except LLMError as e:
            print(f"  Drafting failed: {e}")
            return 1
        print(f"  {llm.summary()}")
        print_draft(d, articles)
        db.save_draft(story.id, "slide", d.to_dict())
        return 0
    finally:
        http.close()
        db.close()


def cmd_news_roundup(cfg: dict, args) -> int:
    """Draft slides for the top draftable stories in the store, so the human sees finished slides."""
    from .pipeline import window
    db = DB(cfg["paths"]["data_dir"] / "socialbot.sqlite")
    http = http_mod.client(float(cfg["news"].get("http_timeout_seconds", 20)))
    try:
        now, since = window(cfg)
        stories = [s for s in db.load_stories(since.isoformat(timespec="seconds"))
                   if s.triage and s.triage.get("draftable") and s.score_parts.get("relevant", True)]
        stories.sort(key=lambda s: (-s.triage["newsworthy"], -s.score))
        n = args.n or int(cfg["news"].get("max_stories", 9))
        picked = stories[:n]
        if not picked:
            print("No draftable triaged stories in the store. Run `socialbot news build` first.")
            return 1
        print(f"Drafting {len(picked)} slide(s) with {cfg['llm']['draft_model']}...")
        llm = LLM(cfg, reuse=args.reuse_llm)
        results = []
        for i, story in enumerate(picked, 1):
            existing = None if args.redraft else db.latest_draft(story.id, "slide")
            print(f"
[{i}/{len(picked)}] {story.triage['headline']}  ({story.triage['newsworthy']}) [{story.id}]")
            if existing:
                print("  using existing draft (pass --redraft to redo)")
                results.append((story, SlideDraft(**existing), []))
                continue
            articles = articles_for(cfg, db, story, http)
            if not any(a.ok for a in articles):
                print("  no usable article text; skipped: " + "; ".join(a.error for a in articles))
                continue
            try:
                d = draft_slide(cfg, llm, story, articles)
            except LLMError as e:
                print(f"  drafting failed: {e}")
                continue
            db.save_draft(story.id, "slide", d.to_dict())
            print_draft(d, articles)
            results.append((story, d, articles))
        print(f"
{llm.summary()}")
        print("
Roundup so far:")
        for story, d, _ in results:
            flag = f"  ⚠ {len(d.warnings)} warning(s)" if d.warnings else ""
            print(f"  - {d.headline}  (confidence {d.confidence}){flag}")
        return 0
    finally:
        http.close()
        db.close()
