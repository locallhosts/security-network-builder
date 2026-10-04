"""Security audit event storage for authentication and operational actions."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCHEMA = """CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 created_at TEXT NOT NULL, event TEXT NOT NULL, subject TEXT NOT NULL DEFAULT '',
 outcome TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_events(created_at);"""


class AuditLog:
    def __init__(self, path: str = "data/audit.db") -> None:
        self.path = path
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:", check_same_thread=False) if path == ":memory:" else None
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self):
        return self._memory or sqlite3.connect(self.path)

    def record(self, event: str, *, subject: str = "", outcome: str = "success", detail: str = "") -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO audit_events(created_at,event,subject,outcome,detail) VALUES(?,?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), event[:100], subject[:200], outcome[:30], detail[:500]),
            )

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id,created_at,event,subject,outcome,detail FROM audit_events ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 500)),),
            ).fetchall()
        return [{"id":r[0],"created_at":r[1],"event":r[2],"subject":r[3],"outcome":r[4],"detail":r[5]} for r in rows]
