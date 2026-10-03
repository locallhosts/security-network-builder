"""Private investigation workspace persistence for the public platform."""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class WorkspaceStore:
    def __init__(self, path: str = "data/workspaces.db") -> None:
        self.path = path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    tags TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS workspace_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    value TEXT NOT NULL,
                    label TEXT,
                    source_url TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE(workspace_id, kind, value),
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS workspace_notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id TEXT NOT NULL,
                    body TEXT NOT NULL,
                    source_url TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS workspace_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    workspace_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create(self, title: str) -> dict[str, Any]:
        wid = str(uuid.uuid4())
        now = self._now()
        with self._lock, self._connect() as db:
            db.execute("INSERT INTO workspaces(id,title,created_at,updated_at) VALUES(?,?,?,?)", (wid, title.strip(), now, now))
            db.execute("INSERT INTO workspace_events(workspace_id,action,detail,created_at) VALUES(?,?,?,?)", (wid, "created", title.strip(), now))
        return self.get(wid)

    def get(self, workspace_id: str) -> dict[str, Any]:
        with self._connect() as db:
            row = db.execute("SELECT * FROM workspaces WHERE id=?", (workspace_id,)).fetchone()
            if not row:
                raise KeyError(workspace_id)
            items = db.execute("SELECT id,kind,value,label,source_url,created_at FROM workspace_items WHERE workspace_id=? ORDER BY id", (workspace_id,)).fetchall()
            notes = db.execute("SELECT id,body,source_url,created_at FROM workspace_notes WHERE workspace_id=? ORDER BY id", (workspace_id,)).fetchall()
            events = db.execute("SELECT id,action,detail,created_at FROM workspace_events WHERE workspace_id=? ORDER BY id", (workspace_id,)).fetchall()
        data = dict(row)
        data["tags"] = json.loads(data["tags"])
        data["items"] = [dict(x) for x in items]
        data["notes"] = [dict(x) for x in notes]
        data["timeline"] = [dict(x) for x in events]
        return data

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute("SELECT id,title,status,tags,created_at,updated_at FROM workspaces ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [{**dict(r), "tags": json.loads(r["tags"])} for r in rows]

    def update(self, workspace_id: str, *, status: str | None = None, tags: list[str] | None = None) -> dict[str, Any]:
        now = self._now()
        fields=[]; values=[]
        if status is not None: fields.append("status=?"); values.append(status)
        if tags is not None: fields.append("tags=?"); values.append(json.dumps(sorted(set(tags))[:30]))
        if fields:
            values.extend([now, workspace_id])
            with self._lock, self._connect() as db:
                cur=db.execute(f"UPDATE workspaces SET {', '.join(fields)}, updated_at=? WHERE id=?", values)
                if cur.rowcount == 0: raise KeyError(workspace_id)
                db.execute("INSERT INTO workspace_events(workspace_id,action,detail,created_at) VALUES(?,?,?,?)", (workspace_id, "updated", json.dumps({"status": status, "tags": tags}), now))
        return self.get(workspace_id)

    def add_item(self, workspace_id: str, kind: str, value: str, label: str | None = None, source_url: str | None = None) -> dict[str, Any]:
        if kind not in {"engineer", "repository"}: raise ValueError("kind must be engineer or repository")
        now=self._now()
        with self._lock, self._connect() as db:
            if not db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone(): raise KeyError(workspace_id)
            db.execute("INSERT OR IGNORE INTO workspace_items(workspace_id,kind,value,label,source_url,created_at) VALUES(?,?,?,?,?,?)", (workspace_id,kind,value,label,source_url,now))
            db.execute("UPDATE workspaces SET updated_at=? WHERE id=?", (now,workspace_id))
            db.execute("INSERT INTO workspace_events(workspace_id,action,detail,created_at) VALUES(?,?,?,?)", (workspace_id, "evidence_added", f"{kind}:{value}", now))
        return self.get(workspace_id)

    def add_note(self, workspace_id: str, body: str, source_url: str | None = None) -> dict[str, Any]:
        if not body.strip(): raise ValueError("note body cannot be empty")
        now=self._now()
        with self._lock, self._connect() as db:
            if not db.execute("SELECT 1 FROM workspaces WHERE id=?", (workspace_id,)).fetchone(): raise KeyError(workspace_id)
            db.execute("INSERT INTO workspace_notes(workspace_id,body,source_url,created_at) VALUES(?,?,?,?)", (workspace_id,body.strip(),source_url,now))
            db.execute("UPDATE workspaces SET updated_at=? WHERE id=?", (now,workspace_id))
            db.execute("INSERT INTO workspace_events(workspace_id,action,detail,created_at) VALUES(?,?,?,?)", (workspace_id, "note_added", body.strip()[:200], now))
        return self.get(workspace_id)

    def delete(self, workspace_id: str) -> None:
        with self._lock, self._connect() as db:
            cur=db.execute("DELETE FROM workspaces WHERE id=?", (workspace_id,))
            if cur.rowcount == 0: raise KeyError(workspace_id)
