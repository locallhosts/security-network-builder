"""Persistent idempotent background job queue backed by SQLite."""
from __future__ import annotations
import json, sqlite3, time, uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
 idempotency_key TEXT UNIQUE, status TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
 max_attempts INTEGER NOT NULL DEFAULT 3, available_at REAL NOT NULL,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL, last_error TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_jobs_ready ON jobs(status, available_at);
"""

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

@dataclass(frozen=True)
class Job:
    id: str
    kind: str
    payload: dict[str, Any]
    status: str
    attempts: int
    max_attempts: int
    available_at: float
    last_error: str

class JobQueue:
    def __init__(self, path: str | Path = "data/jobs.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:", check_same_thread=False) if self.path == ":memory:" else None
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return self._memory or sqlite3.connect(self.path)

    def enqueue(self, kind: str, payload: dict[str, Any], *, idempotency_key: str | None = None,
                max_attempts: int = 3) -> Job:
        if not kind or len(kind) > 100:
            raise ValueError("invalid job kind")
        if max_attempts < 1 or max_attempts > 10:
            raise ValueError("max_attempts must be between 1 and 10")
        job_id = str(uuid.uuid4())
        now = _now()
        with self._conn() as conn:
            try:
                conn.execute(
                    "INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (job_id, kind, json.dumps(payload, separators=(",", ":")), idempotency_key,
                     "queued", 0, max_attempts, time.time(), now, now, ""),
                )
            except sqlite3.IntegrityError:
                if not idempotency_key:
                    raise
                row = conn.execute("SELECT id FROM jobs WHERE idempotency_key=?", (idempotency_key,)).fetchone()
                if not row:
                    raise
                job_id = row[0]
        return self.get(job_id)

    def get(self, job_id: str) -> Job:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id,kind,payload,status,attempts,max_attempts,available_at,last_error FROM jobs WHERE id=?",
                (job_id,),
            ).fetchone()
        if not row:
            raise KeyError(job_id)
        return Job(row[0], row[1], json.loads(row[2]), row[3], row[4], row[5], row[6], row[7])

    def claim(self) -> Job | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM jobs WHERE status='queued' AND available_at<=? ORDER BY created_at LIMIT 1",
                (time.time(),),
            ).fetchone()
            if not row:
                return None
            changed = conn.execute(
                "UPDATE jobs SET status='running',attempts=attempts+1,updated_at=? WHERE id=? AND status='queued'",
                (_now(), row[0]),
            ).rowcount
        return self.get(row[0]) if changed else None

    def succeed(self, job_id: str) -> Job:
        with self._conn() as conn:
            conn.execute("UPDATE jobs SET status='succeeded',updated_at=? WHERE id=?", (_now(), job_id))
        return self.get(job_id)

    def fail(self, job_id: str, error: str, *, retry_delay: float = 5.0) -> Job:
        with self._conn() as conn:
            row = conn.execute("SELECT attempts,max_attempts FROM jobs WHERE id=?", (job_id,)).fetchone()
            if not row:
                raise KeyError(job_id)
            attempts, max_attempts = row
            terminal = attempts >= max_attempts
            conn.execute(
                "UPDATE jobs SET status=?,available_at=?,last_error=?,updated_at=? WHERE id=?",
                ("failed" if terminal else "queued",
                 time.time() + max(0.0, retry_delay), str(error)[:1000], _now(), job_id),
            )
        return self.get(job_id)

    def run_once(self, handlers: dict[str, Callable[[dict[str, Any]], None]]) -> Job | None:
        job = self.claim()
        if not job:
            return None
        handler = handlers.get(job.kind)
        if handler is None:
            return self.fail(job.id, f"no handler for job kind {job.kind}", retry_delay=0)
        try:
            handler(job.payload)
        except Exception as exc:
            return self.fail(job.id, str(exc))
        return self.succeed(job.id)
