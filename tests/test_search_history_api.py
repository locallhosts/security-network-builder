from fastapi.testclient import TestClient

from snb.api.app import app


def test_search_history_api_is_private_and_compares(monkeypatch, tmp_path):
    class FakeClient:
        def __init__(self, token):
            pass

        def search_repositories(self, query, per_page=30, sort="stars", page=1):
            return [
                {
                    "name": "alpha",
                    "full_name": "org/alpha",
                    "html_url": "https://github.com/org/alpha",
                    "owner": {"login": "org"},
                    "stargazers_count": 10,
                    "language": "Python",
                }
            ]

    monkeypatch.setattr("snb.api.app.GitHubClient", FakeClient)
    monkeypatch.setenv("API_KEYS", "secret")
    monkeypatch.setenv("SNB_SEARCH_HISTORY_DB", str(tmp_path / "searches.db"))
    client = TestClient(app)

    assert client.get("/api/search-history").status_code == 401
    created = client.post(
        "/api/search-history",
        json={"name": "cloud", "query": "cloud security", "limit": 10},
        headers={"X-API-Key": "secret"},
    )
    assert created.status_code == 201
    assert created.json()["results"][0]["full_name"] == "org/alpha"

    compare = client.get(
        "/api/search-history/cloud/compare",
        headers={"X-API-Key": "secret"},
    )
    assert compare.status_code == 200
    assert compare.json()["added"][0]["full_name"] == "org/alpha"


def test_search_history_api_rejects_unbounded_input(monkeypatch, tmp_path):
    monkeypatch.setenv("API_KEYS", "secret")
    monkeypatch.setenv("SNB_SEARCH_HISTORY_DB", str(tmp_path / "searches.db"))
    client = TestClient(app)

    response = client.post(
        "/api/search-history",
        json={"name": "x" * 81, "query": "security"},
        headers={"X-API-Key": "secret"},
    )
    assert response.status_code == 422
