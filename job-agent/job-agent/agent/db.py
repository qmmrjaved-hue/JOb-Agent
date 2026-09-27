"""SQLite store for postings already seen, plus run history and source health.

The database file lives in data/agent.db. When the agent runs in GitHub Actions
the workflow commits this file back to the repository after each run, so the
memory of what has already been seen carries over from day to day and across
computers.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path


class SeenDB:
    def __init__(self, path: str = "data/agent.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self._create()

    def _create(self):
        c = self.conn.cursor()
        c.execute(
            """CREATE TABLE IF NOT EXISTS seen (
                   profile TEXT, posting_id TEXT, title TEXT, organization TEXT,
                   url TEXT, source TEXT, posting_type TEXT, relevance INTEGER,
                   first_seen TEXT, notified INTEGER DEFAULT 0,
                   PRIMARY KEY (profile, posting_id) )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS runs (
                   run_at TEXT, profile TEXT, source TEXT,
                   fetched INTEGER, new_relevant INTEGER, error TEXT )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS source_health (
                   source TEXT PRIMARY KEY, zero_streak INTEGER DEFAULT 0,
                   last_count INTEGER, last_seen TEXT )"""
        )
        self.conn.commit()

    # ---- seen postings ----
    def is_seen(self, profile: str, posting_id: str) -> bool:
        r = self.conn.execute(
            "SELECT 1 FROM seen WHERE profile=? AND posting_id=?",
            (profile, posting_id),
        ).fetchone()
        return r is not None

    def mark_seen(self, profile: str, posting, notified: bool = True):
        self.conn.execute(
            """INSERT OR REPLACE INTO seen
               (profile, posting_id, title, organization, url, source,
                posting_type, relevance, first_seen, notified)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (profile, posting.make_id(), posting.title, posting.organization,
             posting.url, posting.source, posting.posting_type,
             posting.relevance_score or 0, datetime.utcnow().isoformat(),
             1 if notified else 0),
        )
        self.conn.commit()

    def seen_keys(self, profile: str, days: int = 60) -> list:
        """title+org keys for recent postings, used by the fuzzy de-duper."""
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            "SELECT title, organization FROM seen WHERE profile=? AND first_seen>=?",
            (profile, cutoff),
        ).fetchall()
        return [f"{r['title']} {r['organization']}".strip().lower() for r in rows]

    def recent_relevant(self, profile: str, days: int = 7, min_score: int = 1) -> list:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            """SELECT * FROM seen WHERE profile=? AND first_seen>=? AND relevance>=?
               ORDER BY relevance DESC""",
            (profile, cutoff, min_score),
        ).fetchall()
        return [dict(r) for r in rows]

    # ---- run history ----
    def record_run(self, profile, source, fetched, new_relevant, error=""):
        self.conn.execute(
            "INSERT INTO runs (run_at, profile, source, fetched, new_relevant, error) VALUES (?,?,?,?,?,?)",
            (datetime.utcnow().isoformat(), profile, source, fetched, new_relevant, error),
        )
        self.conn.commit()

    # ---- source health ----
    def update_source_health(self, source: str, count: int) -> int:
        row = self.conn.execute(
            "SELECT zero_streak FROM source_health WHERE source=?", (source,)
        ).fetchone()
        streak = (row["zero_streak"] if row else 0)
        streak = streak + 1 if count == 0 else 0
        self.conn.execute(
            """INSERT OR REPLACE INTO source_health (source, zero_streak, last_count, last_seen)
               VALUES (?,?,?,?)""",
            (source, streak, count, datetime.utcnow().isoformat()),
        )
        self.conn.commit()
        return streak

    def close(self):
        self.conn.close()
