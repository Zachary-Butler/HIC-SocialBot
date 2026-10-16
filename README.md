# HIC SocialBot

Two lanes, one rule: nothing is published without a logged human approval.

- **News lane** (`socialbot/news/`): the week's important AI stories from reputable outlets → a finished roundup carousel (Canva-filled slides, captions per channel, sources, verification) → one approval → Buffer queue.
- **Social lane** (`socialbot/social/`): what's popular early on X/Reddit/HN → alerts carrying a finished org post → one approval → Buffer.

Shared plumbing lives in `socialbot/core/` (Claude wrapper, DB, voice, Zulip, Buffer, CLI). Lanes share nothing else: not sources, not ranking, not prompts.

Plan and rationale: `C:\Users\zacha\.claude\plans\pasted-content-id-dfb5-this-is-streamed-raccoon.md`.

## Setup

```
uv venv --python 3.10
uv pip install -e ".[dev]"
cp .env.example .env   # fill in keys
uv run socialbot news build --dry-run
```
