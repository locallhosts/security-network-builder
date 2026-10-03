"""Persistent recommendation history with SQLite compatibility and PostgreSQL support."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Recommendation
from .migrations import apply_migrations

STATUSES = {"new", "reviewing", "connected", "ignored"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    created_at TEXT NOT NULL, profile TEXT NOT NULL, api TEXT NOT NULL,
    graph TEXT NOT NULL, orgs TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS recs (
    run_id INTEGER NOT NULL, login TEXT NOT NULL, score REAL NOT NULL,
    data TEXT NOT NULL, PRIMARY KEY (run_id, login)
);
CREATE TABLE IF NOT EXISTS notes (
    login TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL
);
"""


class History:
    """Storage facade. SQLite remains the local default; PostgreSQL is opt-in."""

    def __init__(self, path: str | Path | None = None, *, database_url: str | None = None) -> None:
        self.database_url = database_url or (str(path) if path else os.environ.get("SNB_DATABASE_URL"))
        self.backend = "postgres" if self.database_url and self.database_url.startswith(("postgresql://", "postgres://")) else "sqlite"
        if self.backend == "postgres":
            try:
                import psycopg
            except ImportError as exc:
                raise RuntimeError("PostgreSQL storage requires the 'psycopg' package") from exc
            self._psycopg = psycopg
            self.path = self.database_url
            with self._conn() as conn:
                self._init_postgres(conn)
                apply_migrations(conn, backend="postgres")
        else:
            self.path = self.database_url or "data/history.db"
            if self.path != ":memory:":
                Path(self.path).parent.mkdir(parents=True, exist_ok=True)
            self._memory = sqlite3.connect(":memory:", check_same_thread=False) if self.path == ":memory:" else None
            with self._conn() as conn:
                conn.executescript(_SCHEMA)
                apply_migrations(conn, backend="sqlite")
                conn.commit()

    def _conn(self):
        if self.backend == "postgres":
            return self._psycopg.connect(self.database_url)
        return self._memory or sqlite3.connect(self.path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    def _init_postgres(self, conn) -> None:
        conn.execute("""CREATE TABLE IF NOT EXISTS runs (
            id BIGSERIAL PRIMARY KEY, created_at TEXT NOT NULL, profile TEXT NOT NULL,
            api TEXT NOT NULL, graph TEXT NOT NULL, orgs TEXT NOT NULL)""")
        conn.execute("""CREATE TABLE IF NOT EXISTS recs (
            run_id BIGINT NOT NULL REFERENCES runs(id), login TEXT NOT NULL,
            score DOUBLE PRECISION NOT NULL, data TEXT NOT NULL,
            PRIMARY KEY (run_id, login))""")
        conn.execute("""CREATE TABLE IF NOT EXISTS notes (
            login TEXT PRIMARY KEY, status TEXT NOT NULL, note TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL)""")
        conn.commit()

    def save_run(self, recs: list[Recommendation], profile: str, api: str, graph: dict[str, Any], orgs: list[dict[str, Any]]) -> int:
        with self._conn() as c:
            if self.backend == "postgres":
                row = c.execute(
                    "INSERT INTO runs (created_at,profile,api,graph,orgs) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (self._now(), profile, api, json.dumps(graph), json.dumps(orgs)),
                ).fetchone()
                run_id = row[0]
                c.executemany(
                    "INSERT INTO recs (run_id,login,score,data) VALUES (%s,%s,%s,%s)",
                    [(run_id, r.login, r.score, json.dumps(r.to_dict())) for r in recs],
                )
            else:
                cur = c.execute("INSERT INTO runs (created_at,profile,api,graph,orgs) VALUES (?,?,?,?,?)",
                                (self._now(), profile, api, json.dumps(graph), json.dumps(orgs)))
                run_id = cur.lastrowid
                c.executemany("INSERT INTO recs (run_id,login,score,data) VALUES (?,?,?,?)",
                              [(run_id, r.login, r.score, json.dumps(r.to_dict())) for r in recs])
        return int(run_id)

    def runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._conn() as c:
            q = ("SELECT r.id,r.created_at,r.profile,r.api,(SELECT COUNT(*) FROM recs x WHERE x.run_id=r.id) "
                 "FROM runs r ORDER BY r.id DESC LIMIT " + ("%s" if self.backend == "postgres" else "?"))
            rows = c.execute(q, (limit,)).fetchall()
        return [{"id": i, "created_at": t, "profile": p, "api": a, "count": n} for i,t,p,a,n in rows]

    def latest_run_id(self) -> int | None:
        with self._conn() as c:
            row = c.execute("SELECT MAX(id) FROM runs").fetchone()
        return row[0]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        with self._conn() as c:
            ph = "%s" if self.backend == "postgres" else "?"
            run = c.execute(f"SELECT id,created_at,profile,api,graph,orgs FROM runs WHERE id={ph}", (run_id,)).fetchone()
            if not run: return None
            rows = c.execute(f"SELECT data FROM recs WHERE run_id={ph} ORDER BY score DESC", (run_id,)).fetchall()
        return {"run":{"id":run[0],"created_at":run[1],"profile":run[2],"api":run[3]},
                "recommendations":[json.loads(r[0]) for r in rows],
                "graph":json.loads(run[4]), "organizations":json.loads(run[5])}

    def diff_runs(self, base_id: int, run_id: int, min_move: float = 2.0) -> dict[str, Any] | None:
        with self._conn() as c:
            ph = "%s" if self.backend == "postgres" else "?"
            if not all(c.execute(f"SELECT 1 FROM runs WHERE id={ph}", (i,)).fetchone() for i in (base_id,run_id)): return None
            old = dict(c.execute(f"SELECT login,score FROM recs WHERE run_id={ph}", (base_id,)).fetchall())
            new = dict(c.execute(f"SELECT login,score FROM recs WHERE run_id={ph}", (run_id,)).fetchall())
        movers=[{"login":l,"from":old[l],"to":new[l],"delta":round(new[l]-old[l],1)} for l in old.keys()&new.keys() if abs(new[l]-old[l])>=min_move]
        return {"base":base_id,"run":run_id,"new":[{"login":l,"score":new[l]} for l in sorted(new.keys()-old.keys(),key=lambda l:-new[l])],
                "dropped":[{"login":l,"score":old[l]} for l in sorted(old.keys()-new.keys(),key=lambda l:-old[l])],
                "movers":sorted(movers,key=lambda m:-abs(m["delta"]))}

    def previous_run_id(self, run_id: int) -> int | None:
        with self._conn() as c:
            ph = "%s" if self.backend == "postgres" else "?"
            row=c.execute(f"SELECT MAX(id) FROM runs WHERE id<{ph}",(run_id,)).fetchone()
        return row[0]

    def seen_logins(self) -> set[str]:
        with self._conn() as c:
            return {r[0] for r in c.execute("SELECT DISTINCT login FROM recs")}

    def engineer_history(self, login: str) -> list[dict[str, Any]]:
        with self._conn() as c:
            ph="%s" if self.backend=="postgres" else "?"
            rows=c.execute(f"SELECT r.id,r.created_at,x.score FROM recs x JOIN runs r ON r.id=x.run_id WHERE x.login={ph} ORDER BY r.id",(login,)).fetchall()
        return [{"run_id":i,"created_at":t,"score":s} for i,t,s in rows]

    def set_status(self, login: str, status: str, note: str = "") -> None:
        if status and status not in STATUSES: raise ValueError(f"status must be one of {sorted(STATUSES)} or empty")
        with self._conn() as c:
            if not status:
                ph="%s" if self.backend=="postgres" else "?"
                c.execute(f"DELETE FROM notes WHERE login={ph}",(login,))
            elif self.backend=="postgres":
                c.execute("""INSERT INTO notes (login,status,note,updated_at) VALUES (%s,%s,%s,%s)
                             ON CONFLICT(login) DO UPDATE SET status=EXCLUDED.status,note=EXCLUDED.note,updated_at=EXCLUDED.updated_at""",
                          (login,status,note[:500],self._now()))
            else:
                c.execute("""INSERT INTO notes (login,status,note,updated_at) VALUES (?,?,?,?)
                             ON CONFLICT(login) DO UPDATE SET status=excluded.status,note=excluded.note,updated_at=excluded.updated_at""",
                          (login,status,note[:500],self._now()))

    def statuses(self) -> dict[str, dict[str, str]]:
        with self._conn() as c:
            rows=c.execute("SELECT login,status,note,updated_at FROM notes").fetchall()
        return {l:{"status":s,"note":n,"updated_at":u} for l,s,n,u in rows}


def main(argv: list[str]) -> int:
    p=argparse.ArgumentParser(prog="main.py history",description="Browse past runs and triage state")
    p.add_argument("--db",default="data/history.db")
    p.add_argument("--run",type=int)
    p.add_argument("--login")
    p.add_argument("--set",nargs=2,metavar=("LOGIN","STATUS"))
    p.add_argument("--note",default="")
    p.add_argument("--diff",nargs="?",const="latest",metavar="RUN")
    args=p.parse_args(argv); h=History(args.db)
    if args.diff:
        run_id=h.latest_run_id() if args.diff=="latest" else int(args.diff); base=h.previous_run_id(run_id) if run_id else None
        d=h.diff_runs(base,run_id) if base else None
        if not d: print("Need two runs to compare."); return 1
        print(f"Run {d['base']} -> run {d['run']}")
        print("New: "+(", ".join(f"@{x['login']} ({x['score']:g})" for x in d["new"]) or "none"))
        print("Dropped: "+(", ".join(f"@{x['login']} ({x['score']:g})" for x in d["dropped"]) or "none"))
        print("Movers: "+(", ".join(f"@{m['login']} {m['from']:g}->{m['to']:g} ({m['delta']:+g})" for m in d["movers"]) or "none")
    elif args.set:
        try: h.set_status(args.set[0],args.set[1],args.note)
        except ValueError as exc: print(exc); return 1
        print(f"@{args.set[0]}: {args.set[1] or 'cleared'}")
    elif args.login:
        print("\n".join(f"run {r['run_id']}  {r['created_at']}  score {r['score']:g}" for r in h.engineer_history(args.login)) or "No history for that login.")
    elif args.run:
        data=h.get_run(args.run)
        if not data: print("No such run."); return 1
        for x in data["recommendations"]: print(f"@{x['login']:<24} {x['score']:>5g}  {', '.join(x['matched_domains'])}")
    else:
        for x in h.runs(): print(f"run {x['id']:>3}  {x['created_at']}  {x['count']:>3} engineers  [{x['api']}]  {x['profile']}")
    return 0
