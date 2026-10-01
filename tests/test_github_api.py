import pytest
import requests

from github_api import GitHubClient, NotFoundError, RateLimitError


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

    def get(self, url, **kw):
        self.calls += 1
        return self.responses.pop(0)


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
