"""Persistent local state for deterministic alert events.

This module records alert delivery/acknowledgement state only. It never sends
notifications or contacts external services.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .alerts import changes_since_previous_run
from .history import History

_SCHEMA = """
CREATE TABLE IF NOT EXISTS alert_events (
    id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL UNIQUE,
    base_run INTEGER NOT NULL,
    run_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    login TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    acknowledged_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_alert_events_status ON alert_events(status, created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class AlertStore:
    def __init__(self, path: str | Path = "data/alerts.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:") if self.path == ":memory:" else None
        with self._conn() as db:
            db.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return self._memory or sqlite3.connect(self.path)

    def sync(self, history: History, run_id: int | None = None, *, min_move: float = 2.0) -> list[dict[str, Any]]:
        result = changes_since_previous_run(history, run_id, min_move=min_move)
        if result["base"] is None or result["run"] is None:
            return self.list()
        created = _now()
        with self._conn() as db:
            for alert in result["alerts"]:
                login = str(alert["login"])
                fingerprint = hashlib.sha256(
                    json.dumps(
                        [result["base"], result["run"], alert["type"], login, alert.get("from"), alert.get("to"), alert.get("score")],
                        separators=(",", ":"),
                        sort_keys=True,
                    ).encode()
                ).hexdigest()
                db.execute(
                    """INSERT OR IGNORE INTO alert_events
                       (id,fingerprint,base_run,run_id,type,login,payload,status,created_at)
                       VALUES(?,?,?,?,?,?,?,?,?)""",
                    (
                        str(uuid.uuid4()), fingerprint, int(result["base"]), int(result["run"]),
                        str(alert["type"]), login, json.dumps(alert, separators=(",", ":")),
                        "pending", created,
                    ),
                )
        return self.list()

    def list(self, *, status: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        query = "SELECT id,base_run,run_id,type,login,payload,status,created_at,acknowledged_at FROM alert_events"
        params: list[Any] = []
        if status:
            if status not in {"pending", "acknowledged"}:
                raise ValueError("status must be pending or acknowledged")
            query += " WHERE status=?"
            params.append(status)
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as db:
            rows = db.execute(query, params).fetchall()
        return [
            {
                "id": row[0], "base_run": row[1], "run_id": row[2], "type": row[3],
                "login": row[4], "payload": json.loads(row[5]), "status": row[6],
                "created_at": row[7], "acknowledged_at": row[8],
            }
            for row in rows
        ]

    def acknowledge(self, event_id: str) -> dict[str, Any]:
        with self._conn() as db:
            changed = db.execute(
                "UPDATE alert_events SET status='acknowledged',acknowledged_at=? WHERE id=?",
                (_now(), event_id),
            ).rowcount
        if not changed:
            raise KeyError(event_id)
        return next(item for item in self.list(limit=500) if item["id"] == event_id)
