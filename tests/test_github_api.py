import pytest
import requests

from snb.github_api import GitHubClient, GitHubError, NotFoundError, RateLimitError


class Resp:
    def __init__(self, status=200, json_data=None, headers=None, text=""):
        self.status_code, self._json, self.headers, self.text = status, json_data, headers or {}, text

    def json(self):
        return self._json


class FakeSession(requests.Session):
    def __init__(self, responses):
        super().__init__()
        self.responses = list(responses)
        self.calls = 0
        self.last_url = None
        self.last_params = None

    def get(self, url, **kw):
        self.calls += 1
        self.last_url = url
        self.last_params = kw.get("params")
        return self.responses.pop(0)

    post = get


def client(responses, token="t"):
    sleeps = []
    c = GitHubClient(token, session=FakeSession(responses), sleep=sleeps.append)
    return c, sleeps


def test_token_sets_auth_header():
    c, _ = client([])
    assert c.session.headers["Authorization"] == "Bearer t"


def test_retries_after_rate_limit():
    c, sleeps = client([Resp(403, headers={"Retry-After": "2"}), Resp(200, {"login": "x"})])
    assert c.get_user("x") == {"login": "x"}
    assert sleeps == [3.0]


def test_rate_limit_too_long_raises():
    c, _ = client([Resp(429, headers={"Retry-After": "9999"})])
    with pytest.raises(RateLimitError):
        c.get_user("x")


def test_404_handled():
    c, _ = client([Resp(404), Resp(404)])
    assert c.list_user_repos("ghost") == []
    assert c.get_user("ghost") == {}


def test_search_returns_items():
    c, _ = client([Resp(200, {"items": [{"id": 1}]})])
    assert c.search_repositories("q") == [{"id": 1}]


def test_204_means_empty_list():
    c, _ = client([Resp(204)])
    assert c.list_contributors("o/empty") == []


def test_contributors_filter_bots_and_swallow_errors():
    c, _ = client([Resp(200, [{"login": "a", "type": "User"}, {"login": "dependabot[bot]", "type": "Bot"}]),
                   Resp(403, text="The history or contributor list is too large")])
    assert [u["login"] for u in c.list_contributors("o/r")] == ["a"]
    assert c.list_contributors("o/huge") == []


def test_graphql_requires_token():
    c, _ = client([], token=None)
    with pytest.raises(GitHubError):
        c.graphql("query { viewer { login } }")


def test_graphql_returns_partial_data_and_detects_rate_limit():
    c, _ = client([Resp(200, {"data": {"u0": None}, "errors": [{"type": "NOT_FOUND"}]})])
    data, errors = c.graphql("q")
    assert data == {"u0": None} and errors[0]["type"] == "NOT_FOUND"
    c, _ = client([Resp(200, {"data": None, "errors": [{"type": "RATE_LIMITED"}]})])
    with pytest.raises(RateLimitError):
        c.graphql("q")


def test_rate_limit_and_last_headers():
    c, _ = client([Resp(200, {"resources": {"core": {"limit": 60, "remaining": 59}}}, headers={"X-OAuth-Scopes": "repo"})])
    assert c.rate_limit()["core"]["remaining"] == 59
    assert c.last_headers["X-OAuth-Scopes"] == "repo"


def test_search_passes_page_to_github():
    c, _ = client([Resp(200, {"items": [{"id": 1}]})])
    assert c.search_repositories("q", per_page=10, page=3) == [{"id": 1}]
    assert c.session.last_params["page"] == 3
    assert c.session.last_params["per_page"] == 10
