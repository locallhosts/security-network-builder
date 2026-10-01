import main
from conftest import repo
from github_api import RateLimitError


class FakeClient:
    def __init__(self, token=None, fail_after=None):
        self.users = 0
        self.fail_after = fail_after

    def search_repositories(self, query, per_page=30, sort="stars"):
        return [repo("tracer", "eBPF runtime security", stars=500, owner="alice"),
                repo("rules", "sigma detection rules", stars=50, owner="bob")]

    def list_user_repos(self, login, limit=100):
        self.users += 1
        if self.fail_after is not None and self.users > self.fail_after:
            raise RateLimitError("limit")
        return []

    def get_user(self, login):
        return {"name": login.title(), "bio": "security"}


def run(monkeypatch, tmp_path, client_factory, extra=()):
    monkeypatch.setattr(main, "GitHubClient", client_factory)
    monkeypatch.setattr(main, "load_env", lambda: None)
    args = main.parse_args(["--output-dir", str(tmp_path), "--top", "5", *extra])
    return main.run(args)


def test_end_to_end_writes_reports(monkeypatch, tmp_path, capsys):
    assert run(monkeypatch, tmp_path, FakeClient) == 0
    out = capsys.readouterr().out
    assert "@alice" in out and "Recommended Engineers" in out
    assert len(list(tmp_path.glob("report_*.md"))) == 1
    assert len(list(tmp_path.glob("report_*.json"))) == 1
    assert "Evidence" in next(tmp_path.glob("*.md")).read_text()


def test_partial_results_on_rate_limit(monkeypatch, tmp_path, capsys):
    code = run(monkeypatch, tmp_path, lambda token=None: FakeClient(fail_after=1))
    assert code == 0                                    # degrades gracefully
    assert "@" in capsys.readouterr().out


def test_never_mutates_github(monkeypatch):
    # Guard: the client exposes read-only methods only.
    from github_api import GitHubClient
    public = {n for n in dir(GitHubClient) if not n.startswith("_")}
    assert not {n for n in public if any(v in n for v in ("follow", "star", "post", "put", "delete"))}
