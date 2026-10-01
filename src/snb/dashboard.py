"""Local web dashboard (stdlib http.server, bound to 127.0.0.1 only).

Hardening, because it renders text written by strangers on GitHub:
  * localhost bind + Host header allow-list (blocks DNS rebinding)
  * per-launch CSRF token required on every state-changing request
  * strict CSP with per-launch nonce, no external resources
  * all untrusted text is rendered with textContent in the page script
  * parameterised SQL; login format validated
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .dashboard_page import PAGE
from .history import STATUSES, History

LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$")
MAX_BODY = 4096


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address: tuple[str, int], history: History) -> None:
        super().__init__(address, Handler)
        self.history = history
        self.csrf = secrets.token_urlsafe(32)
        self.nonce = secrets.token_urlsafe(16)
        port = self.server_address[1]
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}


class Handler(BaseHTTPRequestHandler):
    server: DashboardServer
    server_version = "SecurityNetworkBuilder"

    def log_message(self, fmt: str, *args: Any) -> None:  # keep the terminal quiet
        pass

    # -- helpers ---------------------------------------------------------
    def _send(self, code: int, body: bytes, ctype: str, csp: bool = False) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if csp:
            n = self.server.nonce
            self.send_header(
                "Content-Security-Policy",
                f"default-src 'none'; script-src 'nonce-{n}'; style-src 'nonce-{n}'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
            )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: Any) -> None:
        self._send(code, json.dumps(obj).encode(), "application/json; charset=utf-8")

    def _host_ok(self) -> bool:
        return (self.headers.get("Host") or "").lower() in self.server.allowed_hosts

    # -- routes ----------------------------------------------------------
    def do_GET(self) -> None:
        if not self._host_ok():
            return self._json(403, {"error": "bad host"})
        path = urlparse(self.path).path
        h = self.server.history

        if path == "/":
            page = PAGE.replace("__NONCE__", self.server.nonce).replace("__CSRF__", self.server.csrf)
            return self._send(200, page.encode(), "text/html; charset=utf-8", csp=True)
        if path == "/api/runs":
            return self._json(200, {"runs": h.runs(50)})
        if path == "/api/diff":
            q = parse_qs(urlparse(self.path).query)
            try:
                base, run_id = int(q["base"][0]), int(q["run"][0])
            except (KeyError, IndexError, ValueError):
                return self._json(400, {"error": "base and run must be integers"})
            diff = h.diff_runs(base, run_id)
            return self._json(200, diff) if diff else self._json(404, {"error": "run not found"})
        m = re.fullmatch(r"/api/runs/(\d+|latest)", path)
        if m:
            run_id = h.latest_run_id() if m.group(1) == "latest" else int(m.group(1))
            data = h.get_run(run_id) if run_id else None
            if not data:
                return self._json(404, {"error": "run not found"})
            notes = h.statuses()
            for rec in data["recommendations"]:
                n = notes.get(rec["login"])
                rec["status"], rec["note"] = (n["status"], n["note"]) if n else ("", "")
            return self._json(200, data)
        m = re.fullmatch(r"/api/engineer/([^/]+)", path)
        if m:
            if not LOGIN_RE.match(m.group(1)):
                return self._json(400, {"error": "invalid login"})
            return self._json(200, {"history": h.engineer_history(m.group(1))})
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self._host_ok():
            return self._json(403, {"error": "bad host"})
        if urlparse(self.path).path != "/api/status":
            return self._json(404, {"error": "not found"})
        if not secrets.compare_digest(self.headers.get("X-CSRF-Token", ""), self.server.csrf):
            return self._json(403, {"error": "bad csrf token"})
        if (self.headers.get("Content-Type") or "").split(";")[0].strip() != "application/json":
            return self._json(415, {"error": "expected application/json"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self._json(400, {"error": "bad length"})
        if not 0 < length <= MAX_BODY:
            return self._json(413, {"error": "body too large"})
        try:
            body = json.loads(self.rfile.read(length))
            login, status, note = str(body["login"]), str(body.get("status", "")), str(body.get("note", ""))
        except (ValueError, KeyError, TypeError):
            return self._json(400, {"error": "invalid body"})
        if not LOGIN_RE.match(login) or (status and status not in STATUSES):
            return self._json(400, {"error": "invalid login or status"})
        self.server.history.set_status(login, status, note)
        self._json(200, {"ok": True})


def make_server(history: History, port: int = 8765) -> DashboardServer:
    return DashboardServer(("127.0.0.1", port), history)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="main.py dashboard", description="Local dashboard for past runs")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--db", default="data/history.db")
    p.add_argument("--open", action="store_true", help="open the browser")
    args = p.parse_args(argv)
    history = History(args.db)
    if history.latest_run_id() is None:
        print("No runs recorded yet. Run `python src/main.py` first.")
    server = make_server(history, args.port)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    print(f"Dashboard: {url}  (localhost only, Ctrl-C to stop)")
    if args.open:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0
