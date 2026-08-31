"""A local SQLite store, so the server can answer "what changed".

A live Graph call answers what is true right now and nothing else. That leaves
the real question unanswerable, because it is not "how many followers do I have"
but "how many did I gain this week, and which post caused it".

Storing what we fetch turns a lookup tool into an analysis tool for the cost of
one table write per call.

Nothing here is a cache. Reads always go to the network and the store is written
as a side effect, so a stale row can never be served as a live answer.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profile_snapshots (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    account     TEXT    NOT NULL,
    taken_at    TEXT    NOT NULL,
    followers   INTEGER,
    following   INTEGER,
    media_count INTEGER
);
CREATE INDEX IF NOT EXISTS profile_snapshots_account_time
    ON profile_snapshots (account, taken_at DESC);

CREATE TABLE IF NOT EXISTS media_snapshots (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    account        TEXT    NOT NULL,
    media_id       TEXT    NOT NULL,
    taken_at       TEXT    NOT NULL,
    like_count     INTEGER,
    comments_count INTEGER,
    permalink      TEXT,
    posted_at      TEXT
);
CREATE INDEX IF NOT EXISTS media_snapshots_media_time
    ON media_snapshots (media_id, taken_at DESC);
CREATE INDEX IF NOT EXISTS media_snapshots_account_time
    ON media_snapshots (account, taken_at DESC);

-- Hashtag name to id. Not a performance cache: Meta caps an account at 30
-- unique hashtags per rolling 7 days, and every uncached lookup spends one of
-- them permanently. Resolving the same tag twice in a week is a real cost.
CREATE TABLE IF NOT EXISTS hashtag_ids (
    name        TEXT PRIMARY KEY,
    hashtag_id  TEXT NOT NULL,
    resolved_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Store:
    def __init__(self, path: Path):
        self._path = path
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        # WAL so a long read cannot block the write that follows it. The server
        # is single process, but an agent can have several tool calls in flight.
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.executescript(_SCHEMA)
        self._connection.commit()
        self._lock = asyncio.Lock()

    def close(self) -> None:
        self._connection.close()

    # ── writes ────────────────────────────────────────────────────────────────

    async def record_profile(self, account: str, profile: dict[str, Any]) -> None:
        def work() -> None:
            self._connection.execute(
                "INSERT INTO profile_snapshots (account, taken_at, followers, following, "
                "media_count) VALUES (?, ?, ?, ?, ?)",
                (
                    account,
                    _now(),
                    profile.get("followers_count"),
                    profile.get("follows_count"),
                    profile.get("media_count"),
                ),
            )
            self._connection.commit()

        async with self._lock:
            await asyncio.to_thread(work)

    async def record_media(self, account: str, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return

        payload = [
            (
                account,
                str(row.get("id")),
                _now(),
                row.get("like_count"),
                row.get("comments_count"),
                row.get("permalink"),
                row.get("timestamp"),
            )
            for row in rows
            if row.get("id")
        ]

        def work() -> None:
            self._connection.executemany(
                "INSERT INTO media_snapshots (account, media_id, taken_at, like_count, "
                "comments_count, permalink, posted_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                payload,
            )
            self._connection.commit()

        async with self._lock:
            await asyncio.to_thread(work)

    # ── reads ─────────────────────────────────────────────────────────────────

    async def profile_history(self, account: str, limit: int = 30) -> list[dict[str, Any]]:
        def work() -> list[dict[str, Any]]:
            rows = self._connection.execute(
                "SELECT taken_at, followers, following, media_count FROM profile_snapshots "
                "WHERE account = ? ORDER BY taken_at DESC LIMIT ?",
                (account, limit),
            ).fetchall()
            return [dict(r) for r in rows]

        return await asyncio.to_thread(work)

    async def media_movement(self, account: str, limit: int = 25) -> list[dict[str, Any]]:
        """Per post: the earliest and latest reading we hold, and the delta.

        Written as one grouped query rather than a loop over posts, so this stays
        a single round trip however much history accumulates.
        """

        def work() -> list[dict[str, Any]]:
            rows = self._connection.execute(
                """
                WITH bounds AS (
                    SELECT media_id,
                           MIN(taken_at) AS first_at,
                           MAX(taken_at) AS last_at,
                           COUNT(*)      AS readings
                    FROM media_snapshots
                    WHERE account = ?
                    GROUP BY media_id
                    HAVING readings > 1
                )
                SELECT b.media_id,
                       b.first_at,
                       b.last_at,
                       b.readings,
                       f.like_count     AS first_likes,
                       l.like_count     AS last_likes,
                       f.comments_count AS first_comments,
                       l.comments_count AS last_comments,
                       l.permalink      AS permalink,
                       l.posted_at      AS posted_at
                FROM bounds b
                JOIN media_snapshots f
                  ON f.media_id = b.media_id AND f.taken_at = b.first_at
                JOIN media_snapshots l
                  ON l.media_id = b.media_id AND l.taken_at = b.last_at
                ORDER BY (COALESCE(l.like_count, 0) - COALESCE(f.like_count, 0)) DESC
                LIMIT ?
                """,
                (account, limit),
            ).fetchall()

            out = []
            for row in rows:
                item = dict(row)
                item["likes_gained"] = (item["last_likes"] or 0) - (item["first_likes"] or 0)
                item["comments_gained"] = (item["last_comments"] or 0) - (
                    item["first_comments"] or 0
                )
                out.append(item)
            return out

        return await asyncio.to_thread(work)

    # ── hashtag ids ───────────────────────────────────────────────────────────

    async def hashtag_id(self, name: str) -> str | None:
        def work() -> str | None:
            row = self._connection.execute(
                "SELECT hashtag_id FROM hashtag_ids WHERE name = ?", (name.lower(),)
            ).fetchone()
            return row["hashtag_id"] if row else None

        return await asyncio.to_thread(work)

    async def remember_hashtag(self, name: str, hashtag_id: str) -> None:
        def work() -> None:
            self._connection.execute(
                "INSERT OR REPLACE INTO hashtag_ids (name, hashtag_id, resolved_at) "
                "VALUES (?, ?, ?)",
                (name.lower(), hashtag_id, _now()),
            )
            self._connection.commit()

        async with self._lock:
            await asyncio.to_thread(work)

    async def hashtags_resolved_since(self, iso_cutoff: str) -> int:
        """How many unique tags were spent inside the rolling window."""

        def work() -> int:
            row = self._connection.execute(
                "SELECT COUNT(*) AS n FROM hashtag_ids WHERE resolved_at >= ?", (iso_cutoff,)
            ).fetchone()
            return int(row["n"])

        return await asyncio.to_thread(work)
