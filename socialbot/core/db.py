"""SQLite state shared by both lanes. Safe to delete during development; it rebuilds itself,
but story IDs (and so "already drafted" memory) are lost with it."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .approval import ACTIONS, Approval
from ..news.extract import Article
from ..news.models import Story

_SCHEMA = """
CREATE TABLE IF NOT EXISTS stories (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    score REAL NOT NULL DEFAULT 0,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS items (
    canonical_url TEXT PRIMARY KEY,
    story_id TEXT NOT NULL,
    url TEXT NOT NULL,
    title TEXT NOT NULL,
    outlet_domain TEXT,
    tier TEXT,
    published_at TEXT,
    first_seen TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS articles (
    canonical_url TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL,
    ok INTEGER NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    target_id TEXT NOT NULL,
    approver TEXT NOT NULL,
    action TEXT NOT NULL,
    at TEXT NOT NULL,
    note TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS items_story ON items(story_id);
CREATE INDEX IF NOT EXISTS stories_last_seen ON stories(last_seen);
CREATE INDEX IF NOT EXISTS drafts_story ON drafts(story_id);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DB:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # ---- stories ----
    def load_stories(self, since_iso: str) -> list[Story]:
        rows = self.conn.execute("SELECT data FROM stories WHERE last_seen >= ? ORDER BY last_seen", (since_iso,))
        return [Story.from_dict(json.loads(r["data"])) for r in rows]

    def get_story(self, story_id: str) -> Story | None:
        row = self.conn.execute("SELECT data FROM stories WHERE id = ?", (story_id,)).fetchone()
        return Story.from_dict(json.loads(row["data"])) if row else None

    def save_stories(self, stories: list[Story]) -> None:
        with self.conn:
            for st in stories:
                self.conn.execute(
                    "INSERT INTO stories (id, title, first_seen, last_seen, score, data) VALUES (?,?,?,?,?,?) "
                    "ON CONFLICT(id) DO UPDATE SET title=excluded.title, last_seen=excluded.last_seen, "
                    "score=excluded.score, data=excluded.data",
                    (st.id, st.title, st.first_seen, st.last_seen, st.score, json.dumps(st.to_dict(), ensure_ascii=False)))
                for it in st.items:
                    self.conn.execute(
                        "INSERT INTO items (canonical_url, story_id, url, title, outlet_domain, tier, published_at, first_seen) "
                        "VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(canonical_url) DO UPDATE SET story_id=excluded.story_id, "
                        "title=excluded.title, published_at=COALESCE(excluded.published_at, items.published_at)",
                        (it.canonical_url or it.url, st.id, it.url, it.title, it.outlet_domain, it.tier,
                         it.published_at, it.fetched_at or st.last_seen))

    # ---- articles (fetched text, cached so re-drafts don't re-fetch) ----
    def get_article(self, canonical_url: str) -> Article | None:
        row = self.conn.execute("SELECT data FROM articles WHERE canonical_url = ?", (canonical_url,)).fetchone()
        return Article.from_dict(json.loads(row["data"])) if row else None

    def save_article(self, canonical_url: str, art: Article) -> None:
        with self.conn:
            self.conn.execute(
                "INSERT INTO articles (canonical_url, fetched_at, ok, data) VALUES (?,?,?,?) "
                "ON CONFLICT(canonical_url) DO UPDATE SET fetched_at=excluded.fetched_at, ok=excluded.ok, data=excluded.data",
                (canonical_url, art.fetched_at or _now(), int(art.ok), json.dumps(art.to_dict(), ensure_ascii=False)))

    # ---- drafts (everything the bot proposed, for the record and for tuning) ----
    def save_draft(self, story_id: str, kind: str, data: dict) -> int:
        with self.conn:
            cur = self.conn.execute("INSERT INTO drafts (story_id, kind, created_at, data) VALUES (?,?,?,?)",
                                    (story_id, kind, _now(), json.dumps(data, ensure_ascii=False)))
            return int(cur.lastrowid)

    def latest_draft(self, story_id: str, kind: str) -> dict | None:
        row = self.conn.execute("SELECT data FROM drafts WHERE story_id = ? AND kind = ? ORDER BY id DESC LIMIT 1",
                                (story_id, kind)).fetchone()
        return json.loads(row["data"]) if row else None

    # ---- approvals (the record a Buffer post requires) ----
    def record_approval(self, kind: str, target_id: str, approver: str, action: str, note: str = "") -> Approval:
        if action not in ACTIONS:
            raise ValueError(f"approval action must be one of {ACTIONS}, got {action!r}")
        if not approver:
            raise ValueError("an approval needs a named approver")
        at = _now()
        with self.conn:
            cur = self.conn.execute("INSERT INTO approvals (kind, target_id, approver, action, at, note) VALUES (?,?,?,?,?,?)",
                                    (kind, target_id, approver, action, at, note))
        return Approval(id=int(cur.lastrowid), kind=kind, target_id=target_id, approver=approver, action=action, at=at, note=note)

    def approvals_for(self, target_id: str) -> list[Approval]:
        rows = self.conn.execute("SELECT * FROM approvals WHERE target_id = ? ORDER BY id", (target_id,))
        return [Approval(id=r["id"], kind=r["kind"], target_id=r["target_id"], approver=r["approver"],
                         action=r["action"], at=r["at"], note=r["note"]) for r in rows]
