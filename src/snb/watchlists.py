"""Persistent watchlists and scheduled discovery metadata.

Watchlists are local analyst configuration: they contain bounded public-data
filters, never credentials or private GitHub data.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """
CREATE TABLE IF NOT EXISTS watchlists (
 id TEXT PRIMARY KEY,
 name TEXT NOT NULL UNIQUE,
 query TEXT NOT NULL,
 min_score REAL NOT NULL DEFAULT 0,
 domains TEXT NOT NULL DEFAULT '[]',
 enabled INTEGER NOT NULL DEFAULT 1,
 interval_minutes INTEGER NOT NULL DEFAULT 1440,
 next_run_at TEXT,
 last_run_at TEXT,
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_watchlists_due ON watchlists(enabled, next_run_at);
"""

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

class WatchlistStore:
    def __init__(self, path: str | Path = "data/watchlists.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:") if self.path == ":memory:" else None
        with self._conn() as db:
            db.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return self._memory or sqlite3.connect(self.path)

    def create(self, name: str, query: str, *, min_score: float = 0,
               domains: list[str] | None = None, interval_minutes: int = 1440) -> dict[str, Any]:
        if not 1 <= len(name.strip()) <= 120:
            raise ValueError("name must be between 1 and 120 characters")
        if not 2 <= len(query.strip()) <= 100:
            raise ValueError("query must be between 2 and 100 characters")
        if not 15 <= interval_minutes <= 43_200:
            raise ValueError("interval_minutes must be between 15 and 43200")
        now = _now()
        wid = str(uuid.uuid4())
        domains = sorted({d.strip() for d in (domains or []) if d.strip()})[:20]
        with self._conn() as db:
            db.execute(
                "INSERT INTO watchlists(id,name,query,min_score,domains,enabled,interval_minutes,next_run_at,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?,?,?,?)",
                (wid, name.strip(), query.strip(), float(min_score), json.dumps(domains),
                 datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() + interval_minutes * 60, timezone.utc).isoformat(),
                 now, now),
            )
        return self.get(wid)

    def get(self, watchlist_id: str) -> dict[str, Any]:
        with self._conn() as db:
            row = db.execute("SELECT * FROM watchlists WHERE id=?", (watchlist_id,)).fetchone()
        if not row:
            raise KeyError(watchlist_id)
        return self._row(row)

    def list(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        q = "SELECT * FROM watchlists" + (" WHERE enabled=1" if enabled_only else "") + " ORDER BY name"
        with self._conn() as db:
            rows = db.execute(q).fetchall()
        return [self._row(r) for r in rows]

    def due(self, now: str | None = None) -> list[dict[str, Any]]:
        now = now or _now()
        with self._conn() as db:
            rows = db.execute(
                "SELECT * FROM watchlists WHERE enabled=1 AND next_run_at IS NOT NULL AND next_run_at<=? ORDER BY next_run_at",
                (now,),
            ).fetchall()
        return [self._row(r) for r in rows]

    def mark_scheduled(self, watchlist_id: str, *, now: str | None = None) -> dict[str, Any]:
        now_dt = datetime.fromisoformat((now or _now()).replace("Z", "+00:00"))
        item = self.get(watchlist_id)
        next_run = now_dt.timestamp() + int(item["interval_minutes"]) * 60
        now_text = now_dt.astimezone(timezone.utc).isoformat()
        with self._conn() as db:
            db.execute(
                "UPDATE watchlists SET last_run_at=?,next_run_at=?,updated_at=? WHERE id=?",
                (now_text, datetime.fromtimestamp(next_run, timezone.utc).isoformat(), now_text, watchlist_id),
            )
        return self.get(watchlist_id)

    def set_enabled(self, watchlist_id: str, enabled: bool) -> dict[str, Any]:
        with self._conn() as db:
            changed = db.execute("UPDATE watchlists SET enabled=?,updated_at=? WHERE id=?",
                                 (1 if enabled else 0, _now(), watchlist_id)).rowcount
        if not changed:
            raise KeyError(watchlist_id)
        return self.get(watchlist_id)

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        keys = ["id","name","query","min_score","domains","enabled","interval_minutes",
                "next_run_at","last_run_at","created_at","updated_at"]
        data = dict(zip(keys, row))
        data["domains"] = json.loads(data["domains"])
        data["enabled"] = bool(data["enabled"])
        return data
