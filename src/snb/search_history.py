"""Bounded local history for comparing GitHub repository searches over time.

Search snapshots contain only intentionally public GitHub repository metadata.
No credentials or private GitHub data are persisted.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_RESULTS = 30
_MAX_SNAPSHOTS = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_snapshots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    query TEXT NOT NULL,
    created_at TEXT NOT NULL,
    results TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_search_snapshots_name_time
    ON search_snapshots(name, created_at DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _key(item: dict[str, Any]) -> str:
    return str(item.get("full_name") or item.get("html_url") or item.get("name") or "").strip().lower()


def _normalize_result(item: dict[str, Any]) -> dict[str, Any] | None:
    key = _key(item)
    if not key:
        return None
    return {
        "name": str(item.get("name") or "")[:200],
        "full_name": str(item.get("full_name") or "")[:200],
        "url": str(item.get("html_url") or "")[:500],
        "owner": str((item.get("owner") or {}).get("login") or "")[:80],
        "stars": max(0, int(item.get("stargazers_count") or 0)),
        "language": (str(item.get("language"))[:80] if item.get("language") else None),
    }


class SearchHistoryStore:
    """Local bounded snapshot store for deterministic search comparisons."""

    def __init__(self, path: str | Path = "data/search_history.db") -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:") if self.path == ":memory:" else None
        with self._conn() as db:
            db.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        return self._memory or sqlite3.connect(self.path)

    def record(
        self,
        name: str,
        query: str,
        results: list[dict[str, Any]],
        *,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        name = name.strip()
        query = query.strip()
        if not 1 <= len(name) <= 80:
            raise ValueError("name must be between 1 and 80 characters")
        if not 2 <= len(query) <= 100:
            raise ValueError("query must be between 2 and 100 characters")
        normalized: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in results[:_MAX_RESULTS]:
            result = _normalize_result(item)
            if not result:
                continue
            key = _key(result)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(result)
        timestamp = created_at or _now()
        snapshot_id = str(uuid.uuid4())
        with self._conn() as db:
            db.execute(
                "INSERT INTO search_snapshots(id,name,query,created_at,results) VALUES(?,?,?,?,?)",
                (snapshot_id, name, query, timestamp, json.dumps(normalized, separators=(",", ":"))),
            )
            rows = db.execute(
                "SELECT id FROM search_snapshots WHERE name=? ORDER BY created_at DESC, id DESC",
                (name,),
            ).fetchall()
            for (old_id,) in rows[_MAX_SNAPSHOTS:]:
                db.execute("DELETE FROM search_snapshots WHERE id=?", (old_id,))
        return self.get(snapshot_id)

    def get(self, snapshot_id: str) -> dict[str, Any]:
        with self._conn() as db:
            row = db.execute(
                "SELECT id,name,query,created_at,results FROM search_snapshots WHERE id=?",
                (snapshot_id,),
            ).fetchone()
        if not row:
            raise KeyError(snapshot_id)
        return self._row(row)

    def list(self, name: str | None = None, *, limit: int = 20) -> list[dict[str, Any]]:
        if not 1 <= limit <= _MAX_SNAPSHOTS:
            raise ValueError("limit must be between 1 and 20")
        query = "SELECT id,name,query,created_at,results FROM search_snapshots"
        params: list[Any] = []
        if name is not None:
            query += " WHERE name=?"
            params.append(name.strip())
        query += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params.append(limit)
        with self._conn() as db:
            rows = db.execute(query, params).fetchall()
        return [self._row(row) for row in rows]

    def compare(self, name: str, *, snapshot_id: str | None = None) -> dict[str, Any] | None:
        snapshots = self.list(name, limit=_MAX_SNAPSHOTS)
        if snapshot_id is not None:
            current = next((x for x in snapshots if x["id"] == snapshot_id), None)
            if current is None:
                raise KeyError(snapshot_id)
            current_index = snapshots.index(current)
            previous = snapshots[current_index + 1] if current_index + 1 < len(snapshots) else None
        else:
            current = snapshots[0] if snapshots else None
            previous = snapshots[1] if len(snapshots) > 1 else None
        if current is None:
            return None
        if previous is None:
            return {
                "name": current["name"],
                "query": current["query"],
                "current": current,
                "previous": None,
                "added": current["results"],
                "removed": [],
                "changed": [],
            }

        old = {_key(x): (i, x) for i, x in enumerate(previous["results"])}
        new = {_key(x): (i, x) for i, x in enumerate(current["results"])}
        added = [new[k][1] | {"rank": new[k][0] + 1} for k in sorted(new.keys() - old.keys())]
        removed = [old[k][1] | {"rank": old[k][0] + 1} for k in sorted(old.keys() - new.keys())]
        changed: list[dict[str, Any]] = []
        for key in sorted(old.keys() & new.keys()):
            old_rank, old_item = old[key]
            new_rank, new_item = new[key]
            delta = int(new_item["stars"]) - int(old_item["stars"])
            rank_delta = old_rank - new_rank
            if delta or rank_delta:
                changed.append({
                    "repository": new_item["full_name"] or new_item["name"],
                    "url": new_item["url"],
                    "stars_from": old_item["stars"],
                    "stars_to": new_item["stars"],
                    "stars_delta": delta,
                    "rank_from": old_rank + 1,
                    "rank_to": new_rank + 1,
                    "rank_delta": rank_delta,
                })
        return {
            "name": current["name"],
            "query": current["query"],
            "current": current,
            "previous": previous,
            "added": sorted(added, key=lambda x: (x["rank"], x["full_name"])),
            "removed": sorted(removed, key=lambda x: (x["rank"], x["full_name"])),
            "changed": sorted(changed, key=lambda x: (-abs(x["stars_delta"]), -abs(x["rank_delta"]), x["repository"])),
        }

    @staticmethod
    def _row(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": row[0],
            "name": row[1],
            "query": row[2],
            "created_at": row[3],
            "results": json.loads(row[4]),
        }
