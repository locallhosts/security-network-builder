import json

from snb import main
from conftest import repo
from snb.github_api import GitHubClient, RateLimitError
from snb.history import History

STATS = {"followers": 500, "commits": 800, "pull_requests": 50, "reviews": 40, "issues": 5,
         "created_at": "2016-01-01T00:00:00Z", "orgs": ["cilium"]}


class FakeClient:
    """Stands in for GitHubClient; REST and GraphQL surfaces both implemented."""

    def __init__(self, token=None, fail_after=None):
        self.token, self.users, self.fail_after = token, 0, fail_after

    def search_repositories(self, query, per_page=30, sort="stars"):
        return [repo("tracer", "eBPF runtime security", stars=500, owner="alice"),
                repo("rules", "sigma detection rules", stars=50, owner="bob")]

    def list_user_repos(self, login, limit=100):
        self.users += 1
        if self.fail_after is not None and self.users > self.fail_after:
            raise RateLimitError("limit")
        return []

    def get_user(self, login):
        return {"name": login.title(), "bio": "security", "followers": 300, "created_at": "2015-01-01T00:00:00Z"}

    def list_user_orgs(self, login):
        return ["cilium"]

    def list_contributors(self, full_name, limit=30):
        return [{"login": "alice"}, {"login": "carol"}, {"login": "bob"}]

    def graphql(self, query, variables):
        data = {}
        for i, login in enumerate(variables.values()):
            data[f"u{i}"] = {"login": login, "name": login, "bio": None, "company": None, "location": None, "websiteUrl": None,
                             "createdAt": "2016-01-01T00:00:00Z", "followers": {"totalCount": 500},
                             "organizations": {"nodes": [{"login": "cilium"}]},
                             "contributionsCollection": {"totalCommitContributions": 800, "totalPullRequestContributions": 50,
                                                         "totalPullRequestReviewContributions": 40, "totalIssueContributions": 5},
                             "repositories": {"nodes": [{"nameWithOwner": f"{login}/tool", "name": "tool", "description": "ebpf security tool",
                                                         "url": f"https://github.com/{login}/tool", "stargazerCount": 100, "forkCount": 1,
                                                         "pushedAt": "2026-09-20T00:00:00Z", "isArchived": False, "isFork": False,
                                                         "primaryLanguage": {"name": "Go"}, "repositoryTopics": {"nodes": []}}]}}
        return data, []


def run(monkeypatch, tmp_path, factory=FakeClient, token=None, extra=(), history=True):
    monkeypatch.setattr(main, "GitHubClient", factory)
    monkeypatch.setattr(main, "load_env", lambda: None)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    if token:
        monkeypatch.setenv("GITHUB_TOKEN", token)
    flags = ["--history-db", str(tmp_path / "h.db")] if history else ["--no-history"]
    return main.run(main.parse_args(["--output-dir", str(tmp_path), "--top", "5", *flags, *extra]))


def test_rest_end_to_end(monkeypatch, tmp_path, capsys):
    assert run(monkeypatch, tmp_path, history=False) == 0
    out = capsys.readouterr().out
    assert "@alice" in out and "Recommended Engineers" in out and "[REST]" in out and "Why:" in out
    assert len(list(tmp_path.glob("report_*.md"))) == 1
    report = json.loads(next(tmp_path.glob("*.json")).read_text())
    assert set(report) == {"profile", "recommendations", "graph", "organizations"}
    assert report["recommendations"][0]["orgs"] == ["cilium"]          # REST enrichment found orgs
    assert "Reputation" in report["recommendations"][0]["breakdown"]


def test_graphql_mode_used_with_token_and_scores_reputation(monkeypatch, tmp_path, capsys):
    assert run(monkeypatch, tmp_path, token="t", history=False) == 0
    assert "[GRAPHQL]" in capsys.readouterr().out
    recs = json.loads(next(tmp_path.glob("*.json")).read_text())["recommendations"]
    assert {r["login"] for r in recs} == {"alice", "bob"}
    assert all(r["breakdown"]["Reputation"] >= 5 for r in recs)
    assert recs[0]["explanation"].startswith("@")


def test_graphql_without_token_is_a_clear_error(monkeypatch, tmp_path, capsys):
    assert run(monkeypatch, tmp_path, extra=["--api", "graphql"]) == 1
    assert "GITHUB_TOKEN" in capsys.readouterr().err


def test_expand_adds_contributors_and_graph_edges(monkeypatch, tmp_path):
    assert run(monkeypatch, tmp_path, token="t", extra=["--expand", "2"], history=False) == 0
    data = json.loads(next(tmp_path.glob("*.json")).read_text())
    carol = next(r for r in data["recommendations"] if r["login"] == "carol")
    assert carol["via"].startswith("contributor of ")
    assert any("both contribute to" in reason for e in data["graph"]["edges"] for reason in e["reasons"])


def test_history_new_flag_and_ignore_list(monkeypatch, tmp_path):
    db = tmp_path / "h.db"
    assert run(monkeypatch, tmp_path) == 0                                # run 1: nothing is "new"
    h = History(db)
    assert not any(r["is_new"] for r in h.get_run(1)["recommendations"])
    h.set_status("bob", "ignored")

    class Wider(FakeClient):
        def search_repositories(self, *a, **k):
            return super().search_repositories(*a, **k) + [repo("x", "ebpf security", stars=5, owner="dave")]

    assert run(monkeypatch, tmp_path, Wider) == 0                         # run 2
    second = {r["login"]: r for r in History(db).get_run(2)["recommendations"]}
    assert "bob" not in second                                            # your 'ignored' decision is honoured
    assert second["dave"]["is_new"] and not second["alice"]["is_new"]

    assert run(monkeypatch, tmp_path, Wider, extra=["--include-ignored"]) == 0
    assert "bob" in {r["login"] for r in History(db).get_run(3)["recommendations"]}


def test_partial_results_on_rate_limit(monkeypatch, tmp_path, capsys):
    code = run(monkeypatch, tmp_path, lambda token=None: FakeClient(fail_after=1), history=False)
    assert code == 0 and "@" in capsys.readouterr().out


def test_client_is_read_only():
    public = {n for n in dir(GitHubClient) if not n.startswith("_")}
    assert not {n for n in public if any(v in n for v in ("follow", "star", "put", "delete", "create", "post"))}


def test_command_dispatch(monkeypatch, tmp_path, capsys):
    assert main.main(["history", "--db", str(tmp_path / "x.db")]) == 0
    assert main.main(["bogus"]) == 2 and "Unknown command" in capsys.readouterr().err
