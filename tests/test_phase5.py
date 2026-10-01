import json
import threading
import urllib.request

import pytest
import yaml

from snb import __version__, doctor, main
from snb.config import Profile, read_profile_text
from snb.dashboard import make_server
from snb.github_api import GitHubError
from snb.history import History
from snb import history as history_cli
from snb.models import Recommendation


# ---------------------------------------------------------------- doctor
class FakeClient:
    def __init__(self, resources=None, headers=None, gql_error=None, rl_error=None):
        self.resources = resources if resources is not None else {
            "core": {"limit": 5000, "remaining": 4990}, "search": {"limit": 30, "remaining": 30}, "graphql": {"limit": 5000, "remaining": 5000}}
        self.last_headers, self.gql_error, self.rl_error = headers or {}, gql_error, rl_error

    def rate_limit(self):
        if self.rl_error:
            raise self.rl_error
        return self.resources

    def graphql(self, q, v=None):
        if self.gql_error:
            raise self.gql_error
        return {"viewer": {"login": "me"}}, []


def checks(tmp_path, client=None, env=None, offline=False, profile=None):
    return doctor.run_checks(profile, client, offline, str(tmp_path / "d" / "h.db"), str(tmp_path / "r"), env=env or {})


def by_name(cs):
    return {c.name: c for c in cs}


def test_offline_skips_network(tmp_path):
    cs = by_name(checks(tmp_path, offline=True))
    assert cs["Profile"].status == "ok" and cs["Network checks"].status == "info"
    assert "GITHUB_TOKEN" not in cs and cs["Profile github_username"].status == "warn"


def test_healthy_token_setup(tmp_path):
    cs = by_name(checks(tmp_path, FakeClient(), {"GITHUB_TOKEN": "t"}))
    assert cs["GITHUB_TOKEN"].status == "ok" and cs["GraphQL"].status == "ok"
    assert cs["Token scopes"].status == "ok" and cs["Search budget"].status == "ok"
    assert "4990/5000" in cs["GitHub API"].detail


def test_broad_token_scopes_warn(tmp_path):
    cs = by_name(checks(tmp_path, FakeClient(headers={"X-OAuth-Scopes": "repo, admin:org"}), {"GITHUB_TOKEN": "t"}))
    assert cs["Token scopes"].status == "warn" and "no scopes are needed" in cs["Token scopes"].detail


def test_rejected_token_fails_and_stops(tmp_path):
    cs = checks(tmp_path, FakeClient(rl_error=GitHubError("401 for /rate_limit: Bad credentials")), {"GITHUB_TOKEN": "bad"})
    last = cs[-1]
    assert last.name == "GitHub API" and last.status == "fail" and "token rejected" in last.detail


def test_graphql_failure_is_a_warning_not_failure(tmp_path):
    cs = by_name(checks(tmp_path, FakeClient(gql_error=GitHubError("nope")), {"GITHUB_TOKEN": "t"}))
    assert cs["GraphQL"].status == "warn" and "REST fallback" in cs["GraphQL"].detail


def test_anonymous_and_low_search_budget(tmp_path):
    low = {"core": {"limit": 60, "remaining": 60}, "search": {"limit": 10, "remaining": 3}}
    cs = by_name(checks(tmp_path, FakeClient(resources=low), {}))
    assert cs["GITHUB_TOKEN"].status == "warn" and "GraphQL" not in cs
    assert cs["Search budget"].status == "warn" and "only 3 left" in cs["Search budget"].detail


def test_bad_profile_and_unwritable_path_fail(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("domains: {}")
    blocker = tmp_path / "file"
    blocker.write_text("x")
    cs = by_name(doctor.run_checks(str(bad), None, True, str(blocker / "h.db"), str(tmp_path / "r"), env={}))
    assert cs["Profile"].status == "fail" and cs["History directory"].status == "fail"


def test_doctor_cli_exit_codes(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(doctor, "load_env", lambda: None)
    args = ["--offline", "--history-db", str(tmp_path / "d" / "h.db"), "--output-dir", str(tmp_path / "r")]
    assert main.main(["doctor", *args]) == 0 and "Ready" in capsys.readouterr().out
    bad = tmp_path / "bad.yaml"
    bad.write_text("domains: {}")
    assert main.main(["doctor", *args, "--profile", str(bad)]) == 1 and "Not ready" in capsys.readouterr().out


# ---------------------------------------------------------------- packaging
def test_version_flag(capsys):
    assert main.main(["--version"]) == 0 and capsys.readouterr().out.strip() == f"snb {__version__}"


def test_bundled_profile_matches_repo_profile_and_is_valid(tmp_path, monkeypatch):
    repo_copy = yaml.safe_load(open("profiles/security_profile.yaml"))
    monkeypatch.chdir(tmp_path)                                  # no ./profiles here -> bundled fallback
    assert yaml.safe_load(read_profile_text()) == repo_copy      # fails if the two copies drift apart
    assert len(Profile.load().domains) == 6


# ---------------------------------------------------------------- run diff
def rec(login, score):
    return Recommendation(login, "u", score, ["eBPF"], {}, [], [])


def two_runs(h):
    h.save_run([rec("a", 10), rec("b", 20), rec("gone", 5)], "P", "rest", {}, [])
    h.save_run([rec("a", 15), rec("b", 20.5), rec("new1", 9), rec("new2", 30)], "P", "rest", {}, [])


def test_diff_runs(tmp_path):
    h = History(tmp_path / "h.db")
    two_runs(h)
    d = h.diff_runs(1, 2)
    assert [x["login"] for x in d["new"]] == ["new2", "new1"]            # best first
    assert [x["login"] for x in d["dropped"]] == ["gone"]
    assert [(m["login"], m["delta"]) for m in d["movers"]] == [("a", 5.0)]  # b moved 0.5 < threshold
    assert h.diff_runs(1, 99) is None and h.previous_run_id(2) == 1 and h.previous_run_id(1) is None


def test_diff_cli(tmp_path, capsys):
    db = str(tmp_path / "h.db")
    two_runs(History(db))
    assert history_cli.main(["--db", db, "--diff"]) == 0
    out = capsys.readouterr().out
    assert "@new2 (30)" in out and "@gone (5)" in out and "@a 10->15 (+5)" in out
    assert history_cli.main(["--db", str(tmp_path / "empty.db"), "--diff"]) == 1


def test_diff_api(tmp_path):
    h = History(tmp_path / "h.db")
    two_runs(h)
    srv = make_server(h, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]

    def get(path):
        try:
            with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{port}{path}", headers={"Host": f"127.0.0.1:{port}"})) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    try:
        status, body = get("/api/diff?base=1&run=2")
        assert status == 200 and body["new"][0]["login"] == "new2"
        assert get("/api/diff?base=1&run=99")[0] == 404
        assert get("/api/diff?base=x&run=2")[0] == 400
        assert get("/api/diff?base=1")[0] == 400
        assert get("/api/diff?base=1%27%3BDROP%20TABLE%20runs&run=2")[0] == 400   # injection attempt is just a bad int
    finally:
        srv.shutdown()
        srv.server_close()
