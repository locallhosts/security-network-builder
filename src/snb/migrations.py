"""Versioned SQL migrations for durable application storage."""
from __future__ import annotations

import sqlite3
from typing import Any

SQLITE_MIGRATIONS = [
    (1, """CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )"""),
    (2, """CREATE INDEX IF NOT EXISTS idx_recs_login ON recs(login);
            CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
            CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at)"""),
]

POSTGRES_MIGRATIONS = [
    (1, """CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    )"""),
    (2, """CREATE INDEX IF NOT EXISTS idx_recs_login ON recs(login);
            CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at);
            CREATE INDEX IF NOT EXISTS idx_notes_updated_at ON notes(updated_at)"""),
]


def apply_migrations(conn: Any, *, backend: str) -> None:
    migrations = POSTGRES_MIGRATIONS if backend == "postgres" else SQLITE_MIGRATIONS
    if backend == "sqlite":
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)")
    rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    applied = {int(row[0]) for row in rows}
    for version, sql in migrations:
        if version in applied:
            continue
        conn.executescript(sql) if backend == "sqlite" else conn.execute(sql)
        stamp = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        placeholder = "%s" if backend == "postgres" else "?"
        conn.execute(f"INSERT INTO schema_migrations (version, applied_at) VALUES ({placeholder}, {placeholder})",
                     (version, stamp))
        conn.commit()
