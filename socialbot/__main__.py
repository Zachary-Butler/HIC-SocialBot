"""Command line: `socialbot news build`, `socialbot news feeds check`."""

import argparse
import sys
from collections import Counter
from datetime import datetime

from .core.config import ConfigError, load_config
from .core.db import DB
from .core import http as http_mod
from .core.llm import LLM, LLMError
from .news.models import Story
from .news.pipeline import build_stories, gather, window
from .news.resolve import resolve_leads
from .news.triage import run_triage
from .news.commands import cmd_news_draft, cmd_news_roundup


def _age(story: Story, now: datetime) -> str:
    latest = story.latest_published or story.first_seen
    hours = (now - datetime.fromisoformat(latest)).total_seconds() / 3600
    return f"{hours:.0f}h ago" if hours < 48 else f"{hours / 24:.0f}d ago"


def print_stories(stories: list[Story], now: datetime, top: int) -> None:
    for n, st in enumerate(stories[:top], 1):
        outlets = st.outlets
        shown = ", ".join(outlets[:3]) + (f" +{len(outlets) - 3}" if len(outlets) > 3 else "")
        p, t = st.score_parts, st.triage
        head = f"{t['newsworthy']:>3}" if t else f"{st.score:.2f}"
        print(f"{n:>2}. {head}  {(t or {}).get('headline') or st.title}")
        ramps = (t or {}).get("on_ramp") or ", ".join(st.on_ramp_hints) or "none"
        print(f"          {shown} · tier {st.lead.tier} · {p.get('outlets', 1)} outlet(s) · {_age(st, now)} · on-ramp: {ramps}"
              + ("" if p.get("relevant", True) else " · NOT AI-RELATED"))
        if t:
            if t.get("why_it_matters"):
                print(f"          {t['why_it_matters']}")
            notes = []
            if t["risk_flags"]:
                notes.append("flags: " + ", ".join(t["risk_flags"]))
            if not t["draftable"]:
                notes.append("NOT DRAFTABLE: " + t["blocked_because"])
            notes += t.get("flag_notes", [])
            if notes:
                print("          " + " · ".join(notes))
        flag = "" if st.lead.resolved else "   (redirect)"
        print(f"          {st.lead.url}{flag}   [{st.id}]")


def cmd_news_build(cfg: dict, args) -> int:
    now, since = window(cfg, days=args.days)
    print(f"Gathering stories since {since:%Y-%m-%d} from outlet feeds"
          + ("" if args.no_search else " and search feeds") + "...", flush=True)
    items, problems = gather(cfg, now, since, use_search=not args.no_search)
    kinds = Counter(i.source_kind for i in items)
    print(f"  {len(items)} items: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
          + (f" · {len(problems)} source problem(s)" if problems else ""))

    db = None if args.no_db else DB(cfg["paths"]["data_dir"] / "socialbot.sqlite")
    try:
        stories = build_stories(cfg, items, now, since, db)
        multi = sum(1 for s in stories if s.score_parts.get("outlets", 1) > 1)
        relevant = sum(1 for s in stories if s.score_parts.get("relevant"))
        print(f"  {len(stories)} stories ({relevant} AI-related, {multi} covered by more than one outlet)")

        top = args.top or int(cfg["news"].get("max_stories", 9)) * 2
        if args.dry_run:
            print("  (dry run: no Claude triage, no URL decoding)\n")
        else:
            llm = LLM(cfg, reuse=args.reuse_llm)
            print(f"  Triaging the top {args.candidates} with {cfg['llm']['triage_model']}...", flush=True)
            try:
                stories = run_triage(cfg, llm, stories, limit=args.candidates)
            except LLMError as e:
                print(f"  Triage failed: {e}")
            print(f"  {llm.summary()}")
            n = resolve_leads(stories, cfg, limit=top)
            if n:
                print(f"  Decoded {n} Google News redirect(s) for the top stories")
            if db:
                db.save_stories(stories)
            print()
        print_stories(stories, now, top)
    finally:
        if db:
            db.close()

    if problems and args.verbose:
        print("\nSource problems:")
        for ref, why in problems:
            print(f"  - {ref}: {why}")
    elif problems:
        print(f"\n{len(problems)} source problem(s); run with -v or `socialbot news feeds check` to see them.")
    return 0


def cmd_feeds_check(cfg: dict, args) -> int:
    from urllib.parse import quote_plus
    from .news.sources.feeds import BING_URL, GOOGLE_URL, parse_bing, parse_google, parse_outlet_feed
    now, since = window(cfg, days=365)
    http = http_mod.client(float(cfg["news"].get("http_timeout_seconds", 20)))
    ok = bad = 0
    try:
        for outlet in cfg["outlets"]["by_domain"].values():
            for url in outlet["feeds"]:
                try:
                    r = http.get(url)
                    r.raise_for_status()
                    got = parse_outlet_feed(r.content, url, cfg["outlets"], outlet, now, since)
                    newest = max((i.published_at or "" for i in got), default="")
                    status = f"OK   {len(got):>3} entries, newest {newest[:10] or '?'}" if got else "EMPTY (parsed, no entries)"
                    ok += bool(got)
                    bad += not got
                except Exception as e:
                    status = f"FAIL {type(e).__name__}: {str(e)[:90]}"
                    bad += 1
                print(f"{outlet['name']:<28} {status:<48} {url}")
        q = (cfg["news"].get("search") or {}).get("queries", ["AI"])[0]
        for label, url, parse in (("google", GOOGLE_URL.format(q=quote_plus(q + " when:7d")), parse_google),
                                  ("bing", BING_URL.format(q=quote_plus(q)), parse_bing)):
            try:
                r = http.get(url)
                r.raise_for_status()
                got = parse(r.content, q, cfg["outlets"], now, since)
                resolved = sum(1 for i in got if i.resolved)
                print(f"{'search: ' + label:<28} OK   {len(got):>3} entries ({resolved} with direct URLs) for {q!r}")
            except Exception as e:
                print(f"{'search: ' + label:<28} FAIL {type(e).__name__}: {str(e)[:90]}")
    finally:
        http.close()
    print(f"\n{ok} feeds OK, {bad} empty or failing.")
    return 0


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):          # Windows consoles default to cp1252
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="socialbot", description="HIC SocialBot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    news = sub.add_parser("news", help="the roundup lane")
    nsub = news.add_subparsers(dest="news_cmd", required=True)
    b = nsub.add_parser("build", help="gather, cluster, rank and triage the week's stories")
    b.add_argument("--dry-run", action="store_true", help="rank only: no Claude, no URL decoding")
    b.add_argument("--days", type=int, help="override news.window_days")
    b.add_argument("--top", type=int, help="how many stories to print")
    b.add_argument("--candidates", type=int, default=40, help="how many ranked stories Claude triages")
    b.add_argument("--no-search", action="store_true", help="skip Google/Bing News searches (outlet feeds only)")
    b.add_argument("--no-db", action="store_true", help="don't read or write the SQLite store")
    b.add_argument("--reuse-llm", action="store_true", help="replay saved Claude answers (no API calls)")
    b.add_argument("-v", "--verbose", action="store_true")
    d = nsub.add_parser("draft", help="draft the slide for one story from the store")
    d.add_argument("story_id")
    d.add_argument("--reuse-llm", action="store_true", help="replay saved Claude answers (no API calls)")
    d.add_argument("--refresh", action="store_true", help="re-fetch article text instead of using the cache")
    d.add_argument("--force", action="store_true", help="draft even if triage marked the story not draftable")
    r = nsub.add_parser("roundup", help="draft slides for the top draftable stories in the store")
    r.add_argument("--n", type=int, help="how many stories (default news.max_stories)")
    r.add_argument("--reuse-llm", action="store_true", help="replay saved Claude answers (no API calls)")
    r.add_argument("--redraft", action="store_true", help="redraft stories that already have a draft")
    r.add_argument("--refresh", action="store_true", help="re-fetch article text instead of using the cache")
    f = nsub.add_parser("feeds", help="feed maintenance")
    f.add_argument("action", choices=["check"])

    args = parser.parse_args(argv)
    try:
        cfg = load_config()
        if args.cmd == "news" and args.news_cmd == "build":
            return cmd_news_build(cfg, args)
        if args.cmd == "news" and args.news_cmd == "draft":
            return cmd_news_draft(cfg, args)
        if args.cmd == "news" and args.news_cmd == "roundup":
            return cmd_news_roundup(cfg, args)
        if args.cmd == "news" and args.news_cmd == "feeds":
            return cmd_feeds_check(cfg, args)
    except ConfigError as e:
        print(f"Config problem: {e}", file=sys.stderr)
        return 2
    return 1


if __name__ == "__main__":
    sys.exit(main())
