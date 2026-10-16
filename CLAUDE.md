# HIC SocialBot: notes for Claude Code sessions

**Start here: `ROADMAP.md`.** It has the current step, what's blocked, and what's next. At the end of every
session, update its **Now** box, tick checkboxes, add a **Session log** line, and record settled decisions.

Original plan and rationale: `C:\Users\zacha\.claude\plans\pasted-content-id-dfb5-this-is-streamed-raccoon.md`
(local to Zach's machine; ROADMAP.md carries everything a session needs).

## What this is

Two lanes that share plumbing and nothing else:
- `socialbot/news/`: the week's important AI stories from **reputable outlets only** (RSS + Google/Bing News
  searches) → cluster → rank → Claude triage → verified slide drafts → (next) Canva-filled carousel → Buffer.
  Social traction is never an input here.
- `socialbot/social/`: (not built yet) what's popular early on X/Reddit/HN → alerts carrying a finished org post.
- `socialbot/core/`: config, SQLite, the one Claude wrapper (`llm.py`), voice files, outputs (Zulip, Buffer).

## Invariants (don't break these)

- **Nothing is published without a logged human approval.** Buffer code may only queue or post on an
  approval record; never on a schedule. Tests must assert this once `outputs/buffer.py` exists.
- **Model proposes, code decides.** Triage/drafting output is advisory; rules in code (`triage.apply_rules`,
  `draft/lint.py`, `draft/verify.py`) have the last word on election flags, deceased minors, grounding.
- **Every quote and number in a draft must appear in a fetched source** (`verify.py`). A paraphrase in
  quotation marks is a failure, by design.
- **Election flag ⇒ never drafted.** Until Nov 4 2026, elected officials are referred to by role, not name.
- **Images:** real photos, screenshots, graphic design and illustration are fine; nothing generated may look
  photoreal (real faces, people, places).
- **Voice:** `core/voice/social-voice.md` is the social voice (project-owned, Zach's). The HIC website voice kit
  is reference only. Only `rules/compliance.md` and `rules/epistemics.md` are gates.
- Personal accounts (Jon, Will, Zach) are out of scope and not a later phase. Bluesky is cut.

## Working here

- Python 3.10, `uv`. Run things with `uv run socialbot ...`; tests with `uv run pytest -q` (offline, fast).
- Settings in `config.yaml` and `outlets.yaml`; secrets in `.env` (never committed).
- `data/` is local state (SQLite, LLM cache, logs); delete freely, story IDs are lost with it.
- Claude: `claude-sonnet-5-5` for triage, `claude-opus-5-5` for slide copy; structured outputs via
  `output_config.format`; the system prompt is prompt-cached; `--reuse-llm` replays saved answers for $0.
  Read the `claude-api` skill before changing `core/llm.py`.
- Windows shell quirk: Bash heredocs here mangle backslashes. Write/patch files with the Write or Edit tool;
  use Bash to run commands.
- Commit at milestones; commit messages end with the Co-Authored-By line from the session.

## CLI

```
uv run socialbot news feeds check            # which outlet feeds and search feeds respond
uv run socialbot news build [--dry-run]      # gather → cluster → rank → (triage, decode URLs) → store
uv run socialbot news draft <story_id>       # fetch articles, draft one verified slide
uv run socialbot news roundup [--n 6]        # draft slides for the top draftable stories
```
