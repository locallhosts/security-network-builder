from snb.graphql_api import build_query, fetch_users, normalize_user

NODE = {
    "login": "alice", "name": "Alice", "bio": "ebpf", "company": None, "location": None, "websiteUrl": None,
    "createdAt": "2018-01-01T00:00:00Z", "followers": {"totalCount": 120},
    "organizations": {"nodes": [{"login": "cilium"}, None]},
    "contributionsCollection": {"totalCommitContributions": 500, "totalPullRequestContributions": 60,
                                "totalPullRequestReviewContributions": 40, "totalIssueContributions": 5},
    "repositories": {"nodes": [None, {
        "nameWithOwner": "alice/tracer", "name": "tracer", "description": "d", "url": "https://github.com/alice/tracer",
        "stargazerCount": 9, "forkCount": 2, "pushedAt": "2026-09-01T00:00:00Z", "isArchived": False, "isFork": False,
        "primaryLanguage": {"name": "Go"}, "repositoryTopics": {"nodes": [{"topic": {"name": "ebpf"}}]}}]},
}


def test_query_has_one_alias_per_user_and_clamped_repo_limit():
    q = build_query(3, 500)
    assert "u0: user(login: $l0)" in q and "u2: user(login: $l2)" in q and "u3:" not in q
    assert "first: 100" in q          # clamped to GitHub's max page size


def test_normalize_matches_rest_shape():
    n = normalize_user(NODE)
    repo = n["repos"][0]
    assert repo["full_name"] == "alice/tracer" and repo["stargazers_count"] == 9
    assert repo["topics"] == ["ebpf"] and repo["language"] == "Go" and repo["fork"] is False
    assert n["stats"]["orgs"] == ["cilium"] and n["stats"]["followers"] == 120
    assert n["profile"]["name"] == "Alice"


class FakeGQL:
    def __init__(self):
        self.calls = []

    def graphql(self, query, variables):
        self.calls.append(variables)
        data = {f"u{i}": ({**NODE, "login": login} if login != "ghost" else None) for i, login in enumerate(variables.values())}
        return data, []


def test_fetch_users_batches_and_skips_missing():
    c = FakeGQL()
    out = fetch_users(c, [f"u{i}" for i in range(23)] + ["ghost"], 50)
    assert len(c.calls) == 3                       # 24 users / batches of 10
    assert "ghost" not in out and len(out) == 23
