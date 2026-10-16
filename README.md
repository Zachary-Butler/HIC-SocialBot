# HIC SocialBot

Two lanes, one rule: nothing is published without a logged human approval.

- **News lane** (`socialbot/news/`): the week's important AI stories from reputable outlets → a finished
  roundup carousel (Canva-filled slides, captions per channel, sources, verification) → one approval →
  Buffer queue.
- **Social lane** (`socialbot/social/`, not yet built): what's popular early on X/Reddit/HN → alerts carrying a
  finished org post → one approval → Buffer.

Shared plumbing lives in `socialbot/core/` (Claude wrapper, SQLite, voice, Zulip, Buffer, CLI). Lanes share
nothing else: not sources, not ranking, not prompts.

**Where we are and what's next: `ROADMAP.md`.** Conventions for Claude Code sessions: `CLAUDE.md`.

## Setup

```
uv venv --python 3.10
uv pip install -e ".[dev]"
cp .env.example .env            # ANTHROPIC_API_KEY at minimum
uv run pytest -q                # offline test suite
```

## The news lane today

```
uv run socialbot news feeds check          # 24 of 27 outlet feeds alive on Oct 16; Google + Bing searches OK
uv run socialbot news build                # ~1,400 items/week → ~1,100 stories → Claude triage of the top 40 (~$0.07)
uv run socialbot news draft st_xxxxxxxxxx  # one verified slide from the article text (~$0.10)
uv run socialbot news roundup --n 6        # the top six draftable stories as slides
```

`news build --dry-run` skips Claude and URL decoding. `--reuse-llm` replays saved Claude answers for $0, so
prompt and threshold changes can be compared offline.

What a slide draft carries: headline (≤70 chars), body (55–80 words with bolded verbatim quotes or numbers),
every quote and number checked against the fetched articles, attribution notes, image search phrases, an
illustration brief, a confidence score, and warnings from the rule checks (pre-election naming, party labels,
deceased-minor names).

## Next

Canva fill of the roundup design → contact sheet → approve → Buffer queue; then Zulip as the approval
surface; then the social lane after Nov 4.
