# HIC SocialBot roadmap

**Last updated:** Fri Oct 16, 2026 (end of session 1) · **Repo:** github.com/Zachary-Butler/HIC-SocialBot · **Tests:** 55 passing

This is the check-in document. Read the **Now** box first. At the end of every working session, update
**Now**, tick checkboxes, add a line to the **Session log**, and move anything settled into **Decisions**.

---

## ▶ Now

**Step M3.3: make the carousel out of the real Canva template.**

| | |
|---|---|
| **Blocked on** | Canva connector. It's authorized on the HIC account but wasn't attached to session 1 (that session started on a personal account). **Fix: start a new Claude Code session on the HIC account.** |
| **First thing next session** | Confirm Canva works → copy `AI NEWS_9_15_26` (approved) → map each page's text and photo elements → fill one story slide (headline, body, source photo) → export PNG → compare with the original. |
| **Then** | M3.4: one command (`socialbot news carousel`) plus a Claude Code skill so "make a news carousel" produces the finished carousel. |
| **Done when** | You ask Claude Code for a news carousel and ~10 minutes later see a finished carousel in Canva, plus PNGs and a summary of sources, photo credits and anything flagged. |

---

## Where we're headed

Jon's ask (Oct 16): a lightweight pipeline that finds timely AI stories and helps the team post without
forcing everything through the video schedule. **Automate monitoring and drafting, not judgment.**

Zach's bar: **frictionless.** Every suggestion is a finished post (slides, captions, alt text, sources, slot).
Approving is one action. Nothing manual between approve and publish except an optional second check.

Two lanes that share plumbing and nothing else:

```
NEWS LANE (weekly carousel)                          SOCIAL LANE (rapid response, after Nov 4)
reputable outlets (RSS + Google/Bing News)           X (Grok Bot / x_search), Reddit, Hacker News
  → cluster into stories → rank by significance        → velocity: what's taking off early
  → Claude triage (newsworthy, on-ramp, risk flags)    → Claude triage (alert / digest / skip)
  → verified slide copy in the social voice            → a finished org-account post per alert
  → source photos → carousel (Canva template)          
            ↓                                                     ↓
     one approval (CLI now → Zulip reaction later) → Buffer (Will's approvals tab or queue)
```

---

## Status at a glance

| # | Milestone | Status | Target |
|---|---|---|---|
| M0 | Foundations: repo, config, Claude wrapper, store, tests | ✅ Done | Oct 16 |
| M1 | News lane: find, cluster, rank and triage the week's stories | ✅ Done (v1) | Oct 16 |
| M2 | Slide copy you can approve without re-reading the articles | ✅ Done (v1) | Oct 16 |
| M3 | Carousel production: our design, source art, captions | 🟡 **In progress** (▶ M3.3) | Oct 23 |
| M4 | Approve → Buffer (CLI first, then Zulip) | 🟡 Started (Buffer client built) | Oct 26 (CLI) · Nov 6 (Zulip) |
| M5 | Unattended weekly build in the cloud | ⬜ Not started | Nov 8 |
| M6 | Social lane: rapid-response alerts with a finished org post | ⬜ Not started (spike can start now) | Nov 20 |
| M7 | Tune and measure; Dec 18 baseline report | ⬜ Not started | Dec 18 |

---

## Key dates

| Date | What | Source |
|---|---|---|
| Oct 19–23 | Canva template fill, one-command carousel, captions | this plan |
| **Oct 23** | Apply for Reddit API access | Q4 OKR |
| **Oct 26** | First assisted roundup approved from the CLI and sitting in Buffer | this plan |
| **Nov 3** | US midterms. Until Nov 4: no election-flagged stories drafted; officials by role, not name; no ramp-up on campaign-salient content | counsel guidance |
| **Nov 6** | Monitoring-spec meeting with Jon and Jacob: demo the working loop plus the Grok Bot readout | Q4 OKR |
| Nov 8 | First unattended Sunday build | this plan |
| **Nov 14** | AI Reality Check. Swap the closing-slide CTA afterwards | — |
| **Nov 20** | X monitoring test running, alerts flowing to Zulip | Q4 OKR |
| **Dec 18** | Baseline report: alerts fired, acted on, speed; roundups built vs. approved; edit rate | Q4 OKR |

---

## Milestones in detail

### M0 Foundations ✅
- [x] Repo, `uv` env, `config.yaml` / `outlets.yaml` / `.env`, GitHub (private)
- [x] `core/llm.py`: structured outputs, prompt caching, cost tracking, budget cap, refusal fallback, replay cache (`--reuse-llm`)
- [x] `core/db.py` (SQLite): stories with persistent IDs, items, article cache, drafts, approvals, roundups
- [x] Offline test suite with fakes for Claude and Buffer (55 tests)
- [x] `CLAUDE.md` conventions for future sessions

### M1 News lane: find and judge the week's stories ✅
- [x] Outlet list with tiers (wire/national, official, major tech, specialist, local, company, syndicated) and a `never_source` list of partisan or unreliable sites, in either direction
- [x] Sources: 27 outlet RSS feeds (24 alive) + 14 Google News and 14 Bing News search queries
- [x] Clustering: the same event across outlets becomes one story; IDs persist across runs
- [x] Ranking: outlet tier, independent-outlet count (syndicators excluded), recency, on-ramp fit; AI-relevance gate
- [x] Claude triage (Sonnet 5.5): merge duplicates, newsworthiness 0–100, on-ramp, why it matters, risk flags
- [x] Rules in code: election flag ⇒ never drafted; deceased-minor keyword safety net; not-AI ⇒ dropped
- [x] Google News redirect decoding for the top stories
- [ ] Don't repeat last week's stories in this week's roundup (track what was published)
- [ ] Add 3–5 more outlet feeds where search coverage is thin (state AG press releases, Congress committees)

### M2 Slide copy you can approve without re-reading ✅
- [x] Article fetching: browser headers, paywalled outlets tried last, headless-browser fallback, cache
- [x] Slide copy (Opus 5.5) in the project's social voice: headline ≤70 chars, 55–80 words, bolded verbatim quotes and numbers
- [x] Verification: every quote and number must appear in a fetched source, or the draft is redone once, then flagged
- [x] Rule checks: officials by role until Nov 4, no party labels, no names in deceased-minor stories, no CTA on story slides
- [x] Readiness gate: confidence ≥ 60 and no warnings; otherwise kept as "not ready", never auto-included
- [x] Voice files: `social-voice.md` (seed), `exemplars.md` (Sep 15 roundup), `rules/compliance.md`, `rules/epistemics.md`, `facts.md`
- [ ] **Zach + Will edit `social-voice.md`.** The seed is written from meeting notes; drafts get better as it does.

### M3 Carousel production 🟡
- [x] M3.1 Source-photo step: each slide's photo comes from its own articles; logos, placeholders and reused images skipped; credit on the slide ("Photo: CNBC / Getty Images"); wire/stock photos flagged as needing a license
- [x] M3.2 HTML renderer matched to the template (torn paper, grid paper, `#e63946` headline): fallback and preview path
- [ ] **M3.3 ▶ Canva template fill** (needs a session with the Canva connector)
  - [ ] Copy the template; map element IDs for cover, story pages and CTA
  - [ ] Fill text; upload each source photo (`create-upload-url` / `upload-asset-from-url`); swap into the photo frame
  - [ ] Add or remove story pages to match 3–6 stories; export PNGs (and PDF for LinkedIn)
  - [ ] Check text fit in Canva; shorten copy if a box overflows
  - [ ] Decide: Canva fill as the production path vs. the HTML renderer (see Open decisions)
- [ ] M3.4 One command plus a skill
  - [ ] `socialbot news carousel`: scan → draft until N slides are ready → photos → build → open the result
  - [ ] Claude Code skill: "make a news carousel" runs it, fills Canva, shows the contact sheet and the flags
  - [ ] Each run writes a `summary.md`: slide text, sources, photo credits, rights notes, warnings, alternates
- [ ] M3.5 Captions per channel: IG, FB, LinkedIn, X, Threads; alt text per slide; IG first comment with sources
- [ ] M3.6 Cover art and CTA photo taken from the template (not the current placeholders)
- [ ] M3.7 Fallbacks when a story has no usable photo: article screenshot → stock photo (Unsplash/Pexels) → illustration (non-photoreal)

### M4 Approve → Buffer 🟡
- [x] Buffer client: `createPost` / `channels`; refuses to post without a recorded human approval; tested
- [x] Approval records in the store (who, when, what action)
- [x] Publish modes: `will_approves` (lands in Will's Buffer approvals tab) / `zach_approves` (straight to queue)
- [ ] Public hosting for slide images (Cloudflare R2), since Buffer needs public image URLs
- [ ] `socialbot news approve <roundup>` → Buffer posts for each channel, plus the Social Review message text
- [ ] Archive of everything published (SOP §6.2)
- [ ] Zulip surface: roundup message with the contact sheet; ✅ / 👎 / 🚀 reactions; `swap`, `drop`, `edit` commands (needs Jacob's bot)
- [ ] Swap Bluesky → LinkedIn in Buffer (the org is at 7/7 channels)

### M5 Unattended weekly build ⬜
- [ ] Hosting (Fly.io or Railway, ~$5–10/mo; confirm with Jacob); SQLite on a volume; secrets
- [ ] Sunday 20:00 MT build → Zulip message Monday morning
- [ ] Canva without a Claude session: check Canva Connect API access (autofill is Enterprise-only); otherwise unattended builds use the HTML renderer and Canva stays for hand-built runs
- [ ] Failure alerts (a build that didn't run is visible)

### M6 Social lane: rapid response ⬜ (goes live after Nov 4)
- [ ] Grok Bot spike (~8 days): upgrade @HumansInControl to X Premium ($30/mo) or use the free trial; test delivery, fidelity, allowance (go/no-go criteria in the plan)
- [ ] Reddit API application (Oct 23); Hacker News velocity
- [ ] Port the prototype's detection and triage (`HiC_SocialTracker/scanner/detect.py`, `triage.py`)
- [ ] Journalist and outlet watchlist weighting (Reality Check push)
- [ ] Alert = a finished org-account post (X + Threads); ✅ next slot / 🚀 now / 👎 skip
- [ ] Will updates SOP §4.4 (reactive posts on the brand account)

### M7 Tune and measure ⬜
- [ ] Telemetry: built vs. approved, edits per slide, minutes from message to approval
- [ ] Voice loop: diff Will's Buffer edits against drafts weekly and propose `social-voice.md` changes
- [ ] Exemplars refreshed from Buffer's top posts
- [ ] Dec 18 baseline report (OKR)

### Parked (not planned)
Email roundup (Jon undecided) · debunk format · stat cards · personal accounts (out of scope, not a later phase) · Bluesky · comment/DM automation (ManyChat is separate)

---

## Waiting on

| Who | What | Unblocks |
|---|---|---|
| **Zach** | New Claude Code session on the HIC account (attaches Canva, Buffer, Gmail) | M3.3 (now) |
| **Zach** | Buffer API key from publish.buffer.com/settings/api (comms@) → `.env` `BUFFER_API_KEY` | M4 |
| **Zach** | Edit `socialbot/core/voice/social-voice.md`; react to the sample slides | M2 quality |
| **Zach** | X subscription upgrade or Grok Bot trial; Reddit API application (Oct 23) | M6 |
| **Will** | Image policy for source photos (incl. Getty/AP/Reuters); start in `will_approves` mode?; review the `never_source` list; SOP §4.4 | M3, M4, M6 |
| **Jacob** | Zulip bot + `#social-signals` channel; hosting platform | M4 Zulip, M5 |
| **Reaa** | Confirm `AI NEWS_9_15_26` is the template to fill (or point to a cleaner master) | M3.3 |
| **Jon** | Sign-off on the monitoring pitch; Nov 6 spec | M6 |

---

## Open decisions

| Decision | Options | Leaning | Owner |
|---|---|---|---|
| Production renderer | Canva fill (editable, exact design) vs. HTML renderer (no Claude session needed, runs unattended) | Canva for runs you ask for in Claude Code; HTML for unattended runs unless Canva Connect allows filling | Zach, after M3.3 |
| Source photos on posts | Use with credit · license wire/stock first · swap agency photos for stock or illustration | Credit everything; never post an agency photo unlicensed | Will |
| Stories per roundup | 3–6 (template has 6) | 5 | Zach |
| Photo credit on slides | On (current) / off | On | Zach + Will |
| Cadence | Weekly (Sunday build) / twice weekly / on demand | Weekly + `roundup now` | Zach + Jon |

---

## Known issues from live runs (Oct 16)

- **Blocked outlets:** Reuters, Bloomberg, Axios and Forbes refuse article fetches, even from a headless browser. Stories covered only by them can't be drafted ("Rogue AI agents broke into Indian firms" was skipped). Mitigation: other outlets usually cover the same event; consider more feeds.
- **Video pages** (e.g. CNBC video) give almost no text → a low-confidence slide → correctly held back as "not ready".
- **Missing photos:** some articles have no usable og:image (the Quartz story rendered with a dark placeholder). Fix in M3.7.
- **Placeholder cover and CTA:** the cover uses a collage of the week's photos and the CTA has no photo until the template's art comes over (M3.6).
- **Pre-election phrasing:** "Iowa's attorney general" instead of names reads stiffly; this relaxes on Nov 4.
- **Triage over-flagging:** `election` was put on Kroger layoffs before the prompt was tightened; keep an eye on it.
- **Claude Code on Windows:** Bash heredocs mangle backslashes. Write and patch files with the Write/Edit tools.

---

## Decisions (settled; don't re-litigate)

| Date | Decision |
|---|---|
| Oct 16 | Standalone news pipeline; doesn't depend on Daily Clips or Will's Playbook |
| Oct 16 | Build new in this repo; port proven pieces from `HiC_SocialTracker`; the prototype stays as reference |
| Oct 16 | Two lanes with separate sourcing: the news lane uses reputable outlets only; the social scanner finds early popularity and feeds rapid response only |
| Oct 16 | Rapid response is the **org account only**; personal accounts are out of scope, not a later phase |
| Oct 16 | Bluesky cut; LinkedIn takes its Buffer slot |
| Oct 16 | Avoid paying for the X API if possible: Grok Bot spike first, then xAI `x_search`, then the X API |
| Oct 16 | Image policy: real photos, screenshots, graphics and AI illustration are fine; nothing generated may look photoreal |
| Oct 16 | Carousels use art from the news sources, credited, with rights flags |
| Oct 16 | v1 format is the news roundup only |
| Oct 16 | Social voice is project-owned and new; the website voice kit is reference, not a gate |
| Oct 16 | Frictionless: the bot builds first and shows a finished post; one action approves; no auto-publish ever |
| Oct 16 | Human surfaces: Zulip + Buffer; cloud-hosted for unattended runs |

---

## Costs (Claude API, measured Oct 16)

| Step | Model | Cost |
|---|---|---|
| Weekly build + triage of the top 40 stories | Sonnet 5.5 | ~$0.07 |
| One slide (draft + verify + occasional redraft) | Opus 5.5 | ~$0.05–0.12 |
| Full 5-story carousel | — | **~$0.50–0.80** |

Expected monthly cost: hosting ~$5–10 · Claude ~$5–15 · X monitoring ~$30 (Grok Bot via X Premium) or usage-based.

---

## How to run (today)

```
uv run socialbot news feeds check      # which feeds and searches respond
uv run socialbot news build            # gather → cluster → rank → triage the top 40 → store   (~3 min)
uv run socialbot news roundup --n 6    # draft and verify slides for the top draftable stories (~1 min each)
uv run socialbot news preview          # pick photos, render slides + contact sheet into data/roundups/<id>/
uv run pytest -q                       # offline tests
```

---

## Session log

**Session 1 (Oct 16).** Scoped the project with Zach from the Comms <> ED meeting, the Q4 OKRs, the draft
image/text SOP, the HiC_SocialTracker prototype and the Sep 15 Canva roundup. Built M0–M2 and most of M3.
First live run: 1,475 items → 1,166 stories → triage → 5 drafted slides, 4 ready (OpenAI state suits;
Anthropic self-replication warning; Character.AI bankruptcy + states; NYC comptroller on Anthropic's IPO).
Rendered with source photos (`data/roundups/rd_20261016-2246/`). Canva, Buffer and Gmail connectors dropped
when the session switched to a personal account → next session starts on the HIC account.
