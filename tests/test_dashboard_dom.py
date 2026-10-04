"""Runs the dashboard in jsdom (Node) against a live server seeded with hostile data.

Skipped when Node or jsdom is unavailable:  cd tests/web && npm ci
"""
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from snb.dashboard import make_server
from snb.graph import build_graph
from snb.history import History
from snb.models import Recommendation
from snb.orgs import analyze_orgs

WEB = Path(__file__).parent / "web"
pytestmark = pytest.mark.skipif(
    not shutil.which("node") or not (WEB / "node_modules" / "jsdom").exists(),
    reason="needs node and `npm ci` in tests/web",
)

XSS = "window.__pwned=1"


def rec(login, score, domains, **kw):
    return Recommendation(login, f"https://github.com/{login}", score, domains, {"x": score}, [f"evidence for {login}"], [], orgs=["cilium"], **kw)


def seed(history):
    def save(recs):
        history.save_run(recs, "Test", "rest", build_graph(recs).to_dict(), analyze_orgs(recs))

    alice = rec("alice", 20, ["eBPF", "Detection"])
    alice.url = "javascript:alert(1)"                                   # hostile profile URL
    alice.profile = {"name": f'<img src=x onerror="{XSS}">', "bio": f"<script>{XSS}</script>", "company": "javascript:alert(1)"}
    alice.explanation = f'"><svg onload={XSS}>'
    alice.evidence = ["<b>not bold</b>"]
    alice.matched_repos = [{"name": f"alice/<img src=x onerror={XSS}>", "url": f"javascript:{XSS}", "stars": 5, "language": "Go", "description": None}]
    save([alice, rec("bob", 25, ["eBPF"]), rec("dave", 12, ["AppSec"])])             # run 1
    alice2 = Recommendation(**{**alice.__dict__, "score": 30})
    save([alice2, rec("bob", 25, ["eBPF"]), rec("carol", 18, ["Cloud"])])             # run 2


def test_dashboard_in_real_dom(tmp_path):
    history = History(tmp_path / "h.db")
    seed(history)
    srv = make_server(history, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        out = subprocess.run(
            ["node", str(WEB / "dom_test.js"), f"http://127.0.0.1:{srv.server_address[1]}/"],
            capture_output=True, text=True, timeout=90,
        )
    finally:
        srv.shutdown()
        srv.server_close()
    assert out.returncode == 0, out.stdout + out.stderr
    assert "DOM OK" in out.stdout


def test_public_page_separates_discovery_from_intelligence_graph():
    """The public UX must not present repository search as the canonical graph builder."""
    from snb.api.app import PUBLIC_PAGE

    assert "GitHub discovery" in PUBLIC_PAGE
    assert "Security Intelligence Graph" in PUBLIC_PAGE
    assert "does not modify the Security Intelligence Graph" in PUBLIC_PAGE
    assert "Refresh intelligence" in PUBLIC_PAGE
    assert "Build graph from search" not in PUBLIC_PAGE
    assert "buildGraphFromSearch" not in PUBLIC_PAGE


def test_public_page_javascript_parses():
    """Catch inline public-page JavaScript syntax errors before deployment."""
    from snb.api.app import PUBLIC_PAGE

    marker = "<script>"
    start = PUBLIC_PAGE.find(marker)
    assert start >= 0, "public page must contain its application script"
    start += len(marker)
    end = PUBLIC_PAGE.find("</script>", start)
    assert end >= 0, "public page application script must be closed"

    script = PUBLIC_PAGE[start:end]
    result = subprocess.run(
        ["node", "--check", "--input-type=commonjs"],
        input=script,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr