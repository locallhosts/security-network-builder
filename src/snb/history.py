"""Recommendation history and triage state (SQLite, stdlib only).

Also stores *your* decisions (reviewing / connected / ignored). The tool never
acts on GitHub itself; this is only a notebook so you can track who you reviewed.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Recommendation

STATUSES = {"new", "reviewing", "connected", "ignored"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
    profile TEXT NOT NULL, api TEXT NOT NULL, graph TEXT NOT NULL, orgs TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS recs (
    run_id INTEGER NOT NULL REFERENCES runs(id), login TEXT NOT NULL,
    score REAL NOT NULL, data TEXT NOT NULL, PRIMARY KEY (run_id, login));
CREATE TABLE IF NOT EXISTS notes (
    login TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
"""


class History:
    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._memory = sqlite3.connect(":memory:", check_same_thread=False) if self.path == ":memory:" else None
        with self._conn() as c:
            c.executescript(_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        # One short-lived connection per operation keeps the threaded dashboard safe.
        return self._memory or sqlite3.connect(self.path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # -- runs ------------------------------------------------------------
    def save_run(self, recs: list[Recommendation], profile: str, api: str, graph: dict[str, Any], orgs: list[dict[str, Any]]) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO runs (created_at, profile, api, graph, orgs) VALUES (?,?,?,?,?)",
                (self._now(), profile, api, json.dumps(graph), json.dumps(orgs)),
            )
            run_id = cur.lastrowid
            c.executemany(
                "INSERT INTO recs (run_id, login, score, data) VALUES (?,?,?,?)",
                [(run_id, r.login, r.score, json.dumps(r.to_dict())) for r in recs],
            )
        return int(run_id)

    def runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT r.id, r.created_at, r.profile, r.api, (SELECT COUNT(*) FROM recs WHERE run_id = r.id) "
                "FROM runs r ORDER BY r.id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"id": i, "created_at": t, "profile": p, "api": a, "count": n} for i, t, p, a, n in rows]

    def latest_run_id(self) -> int | None:
        with self._conn() as c:
            row = c.execute("SELECT MAX(id) FROM runs").fetchone()
        return row[0]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            run = c.execute("SELECT id, created_at, profile, api, graph, orgs FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not run:
                return None
            rows = c.execute("SELECT data FROM recs WHERE run_id = ? ORDER BY score DESC", (run_id,)).fetchall()
        return {
            "run": {"id": run[0], "created_at": run[1], "profile": run[2], "api": run[3]},
            "recommendations": [json.loads(r[0]) for r in rows],
            "graph": json.loads(run[4]),
            "organizations": json.loads(run[5]),
        }

    def diff_runs(self, base_id: int, run_id: int, min_move: float = 2.0) -> dict[str, Any] | None:
        """What changed between two runs: new engineers, dropped engineers, big score movers."""
        with self._conn() as c:
            if not all(c.execute("SELECT 1 FROM runs WHERE id = ?", (i,)).fetchone() for i in (base_id, run_id)):
                return None
            old = dict(c.execute("SELECT login, score FROM recs WHERE run_id = ?", (base_id,)).fetchall())
            new = dict(c.execute("SELECT login, score FROM recs WHERE run_id = ?", (run_id,)).fetchall())
        movers = [
            {"login": l, "from": old[l], "to": new[l], "delta": round(new[l] - old[l], 1)}
            for l in old.keys() & new.keys() if abs(new[l] - old[l]) >= min_move
        ]
        return {
            "base": base_id,
            "run": run_id,
            "new": [{"login": l, "score": new[l]} for l in sorted(new.keys() - old.keys(), key=lambda l: -new[l])],
            "dropped": [{"login": l, "score": old[l]} for l in sorted(old.keys() - new.keys(), key=lambda l: -old[l])],
            "movers": sorted(movers, key=lambda m: -abs(m["delta"])),
        }

    def previous_run_id(self, run_id: int) -> int | None:
        with self._conn() as c:
            row = c.execute("SELECT MAX(id) FROM runs WHERE id < ?", (run_id,)).fetchone()
        return row[0]

    # -- per engineer ------------------------------------------------------
    def seen_logins(self) -> set[str]:
        with self._conn() as c:
            return {r[0] for r in c.execute("SELECT DISTINCT login FROM recs")}

    def engineer_history(self, login: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT r.id, r.created_at, x.score FROM recs x JOIN runs r ON r.id = x.run_id "
                "WHERE x.login = ? ORDER BY r.id",
                (login,),
            ).fetchall()
        return [{"run_id": i, "created_at": t, "score": s} for i, t, s in rows]

    # -- triage state --------------------------------------------------------
    def set_status(self, login: str, status: str, note: str = "") -> None:
        if status and status not in STATUSES:
            raise ValueError(f"status must be one of {sorted(STATUSES)} or empty")
        with self._conn() as c:
            if not status:
                c.execute("DELETE FROM notes WHERE login = ?", (login,))
            else:
                c.execute(
                    "INSERT INTO notes (login, status, note, updated_at) VALUES (?,?,?,?) "
                    "ON CONFLICT(login) DO UPDATE SET status=excluded.status, note=excluded.note, updated_at=excluded.updated_at",
                    (login, status, note[:500], self._now()),
                )

    def statuses(self) -> dict[str, dict[str, str]]:
        with self._conn() as c:
            rows = c.execute("SELECT login, status, note, updated_at FROM notes").fetchall()
        return {l: {"status": s, "note": n, "updated_at": u} for l, s, n, u in rows}


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="main.py history", description="Browse past runs and triage state")
    p.add_argument("--db", default="data/history.db")
    p.add_argument("--run", type=int, help="show one run")
    p.add_argument("--login", help="score trend for one engineer")
    p.add_argument("--set", nargs=2, metavar=("LOGIN", "STATUS"), help=f"set status ({'/'.join(sorted(STATUSES))}, or '' to clear)")
    p.add_argument("--note", default="")
    p.add_argument("--diff", nargs="?", const="latest", metavar="RUN", help="what changed in RUN (default: latest) vs the run before it")
    args = p.parse_args(argv)
    h = History(args.db)

    if args.diff:
        run_id = h.latest_run_id() if args.diff == "latest" else int(args.diff)
        base = h.previous_run_id(run_id) if run_id else None
        d = h.diff_runs(base, run_id) if base else None
        if not d:
            print("Need two runs to compare.")
            return 1
        print(f"Run {d['base']} -> run {d['run']}")
        print("New:     " + (", ".join(f"@{x['login']} ({x['score']:g})" for x in d["new"]) or "none"))
        print("Dropped: " + (", ".join(f"@{x['login']} ({x['score']:g})" for x in d["dropped"]) or "none"))
        print("Movers:  " + (", ".join(f"@{m['login']} {m['from']:g}->{m['to']:g} ({m['delta']:+g})" for m in d["movers"]) or "none"))
    elif args.set:
        try:
            h.set_status(args.set[0], args.set[1], args.note)
        except ValueError as exc:
            print(exc)
            return 1
        print(f"@{args.set[0]}: {args.set[1] or 'cleared'}")
    elif args.login:
        rows = h.engineer_history(args.login)
        print("\n".join(f"run {r['run_id']}  {r['created_at']}  score {r['score']:g}" for r in rows) or "No history for that login.")
    elif args.run:
        data = h.get_run(args.run)
        if not data:
            print("No such run.")
            return 1
        for r in data["recommendations"]:
            print(f"@{r['login']:<24} {r['score']:>5g}  {', '.join(r['matched_domains'])}")
    else:
        for r in h.runs():
            print(f"run {r['id']:>3}  {r['created_at']}  {r['count']:>3} engineers  [{r['api']}]  {r['profile']}")
    return 0
