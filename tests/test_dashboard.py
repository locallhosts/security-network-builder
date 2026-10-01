import json
import threading
import urllib.error
import urllib.request

import pytest

from snb.dashboard import make_server
from snb.history import History
from snb.models import Recommendation


@pytest.fixture
def server(tmp_path):
    h = History(tmp_path / "h.db")
    r = Recommendation("alice", "https://github.com/alice", 20, ["eBPF"], {"eBPF": 10}, ["e"], [], explanation="<script>x</script>")
    h.save_run([r], "P", "rest", {"nodes": [], "edges": [], "communities": []}, [])
    srv = make_server(h, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield srv, h
    srv.shutdown()
    srv.server_close()


def call(srv, path, method="GET", body=None, headers=None):
    port = srv.server_address[1]
    hdrs = {"Host": f"127.0.0.1:{port}", **(headers or {})}
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, method=method, headers=hdrs)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.headers, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read()


def test_binds_to_localhost_only(server):
    assert server[0].server_address[0] == "127.0.0.1"


def test_page_has_csp_nonce_and_csrf(server):
    srv, _ = server
    status, headers, body = call(srv, "/")
    csp = headers["Content-Security-Policy"]
    assert status == 200 and f"'nonce-{srv.nonce}'" in csp and "default-src 'none'" in csp
    assert srv.csrf in body.decode() and "innerHTML" not in body.decode()


def test_api_returns_run_with_status_merge(server):
    srv, h = server
    h.set_status("alice", "reviewing", "n")
    status, _, body = call(srv, "/api/runs/latest")
    rec = json.loads(body)["recommendations"][0]
    assert status == 200 and rec["status"] == "reviewing" and rec["note"] == "n"
    assert call(srv, "/api/runs/999")[0] == 404
    assert json.loads(call(srv, "/api/engineer/alice")[2])["history"][0]["score"] == 20
    assert call(srv, "/api/engineer/..%2Fetc")[0] == 400


def test_rejects_foreign_host_header(server):
    srv, _ = server
    assert call(srv, "/api/runs", headers={"Host": "evil.example:80"})[0] == 403


def test_post_requires_csrf_json_and_valid_values(server):
    srv, h = server
    ok = json.dumps({"login": "alice", "status": "connected", "note": "hi"}).encode()
    js = {"Content-Type": "application/json"}
    assert call(srv, "/api/status", "POST", ok, js)[0] == 403                                   # no token
    assert call(srv, "/api/status", "POST", ok, {**js, "X-CSRF-Token": "wrong"})[0] == 403
    assert call(srv, "/api/status", "POST", ok, {"Content-Type": "text/plain", "X-CSRF-Token": srv.csrf})[0] == 415
    bad = json.dumps({"login": "alice", "status": "followed"}).encode()
    assert call(srv, "/api/status", "POST", bad, {**js, "X-CSRF-Token": srv.csrf})[0] == 400
    big = b"x" * 5000
    assert call(srv, "/api/status", "POST", big, {**js, "X-CSRF-Token": srv.csrf})[0] == 413
    assert call(srv, "/api/status", "POST", ok, {**js, "X-CSRF-Token": srv.csrf})[0] == 200
    assert h.statuses()["alice"]["status"] == "connected"
