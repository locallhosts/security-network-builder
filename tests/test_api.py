from fastapi.testclient import TestClient

from snb.api.app import app


def test_home_page():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    assert "Security Network Builder" in response.text


def test_health():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_protected_endpoint_requires_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = TestClient(app)
    assert client.get("/api/runs").status_code == 401
    assert client.get("/api/runs", headers={"X-API-Key": "secret"}).status_code == 200


def test_search_is_public_even_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_repositories",
        lambda self, query, per_page=30: [{"full_name": "acme/ebpf", "description": "runtime security", "stargazers_count": 4, "language": "Go", "owner": {"login": "acme"}, "html_url": "https://github.com/acme/ebpf"}],
    )
    client = TestClient(app)
    response = client.get("/api/search?q=ebpf")
    assert response.status_code == 200
    assert response.json()["results"][0]["repository"] == "acme/ebpf"


def test_graph_is_public_even_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = TestClient(app)
    assert client.get("/api/graph").status_code == 200


def test_security_headers_and_github_url_validation(monkeypatch):
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_repositories",
        lambda self, query, per_page=30: [
            {"full_name": "acme/safe", "html_url": "https://github.com/acme/safe"},
            {"full_name": "acme/unsafe", "html_url": "https://evil.example/acme/unsafe"},
        ],
    )
    response = TestClient(app).get("/api/search?q=security")
    assert response.status_code == 200
    assert response.json()["results"][0]["url"] == "https://github.com/acme/safe"
    assert response.json()["results"][1]["url"] is None
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Cache-Control"] == "no-store"


def test_search_validates_query_and_limit():
    client = TestClient(app)
    assert client.get("/api/search?q=x").status_code == 422
    assert client.get("/api/search?q=security&limit=31").status_code == 422


def test_search_translates_github_error_to_502(monkeypatch):
    from snb.github_api import GitHubError

    def fail(*args, **kwargs):
        raise GitHubError("upstream unavailable")

    monkeypatch.setattr("snb.api.app.GitHubClient.search_repositories", fail)
    response = TestClient(app).get("/api/search?q=security")
    assert response.status_code == 502
    assert response.json()["detail"] == "upstream unavailable"


def test_private_route_rejects_wrong_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    response = TestClient(app).get("/api/runs", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "invalid API key"


def test_private_route_is_unprotected_when_api_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    response = TestClient(app).get("/api/runs")
    assert response.status_code == 200


def test_runs_limit_is_bounded():
    client = TestClient(app)
    assert client.get("/api/runs?limit=0").status_code == 422
    assert client.get("/api/runs?limit=101").status_code == 422


def test_run_lookup_validates_positive_id():
    client = TestClient(app)
    assert client.get("/api/runs/0").status_code == 404


def test_latest_run_returns_404_when_history_is_empty(monkeypatch):
    class EmptyHistory:
        def latest_run_id(self):
            return None

    monkeypatch.setattr("snb.api.app.get_history", lambda: EmptyHistory())
    response = TestClient(app).get("/api/runs/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == "no runs recorded"


def test_latest_run_returns_404_when_run_disappears(monkeypatch):
    class MissingHistory:
        def latest_run_id(self):
            return 7

        def get_run(self, run_id):
            return None

    monkeypatch.setattr("snb.api.app.get_history", lambda: MissingHistory())
    response = TestClient(app).get("/api/runs/latest")
    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_run_lookup_returns_404_for_unknown_run(monkeypatch):
    class MissingHistory:
        def get_run(self, run_id):
            return None

    monkeypatch.setattr("snb.api.app.get_history", lambda: MissingHistory())
    response = TestClient(app).get("/api/runs/999")
    assert response.status_code == 404
    assert response.json()["detail"] == "run not found"


def test_engineer_history_contract(monkeypatch):
    class HistoryStub:
        def engineer_history(self, login):
            return [{"run_id": 1, "score": 12}]

    monkeypatch.setattr("snb.api.app.get_history", lambda: HistoryStub())
    response = TestClient(app).get("/api/engineers/alice")
    assert response.status_code == 200
    assert response.json() == {"login": "alice", "history": [{"run_id": 1, "score": 12}]}


def test_search_rate_limit_returns_retry_after(monkeypatch):
    import snb.api.app as api_app

    api_app._search_hits.clear()
    monkeypatch.setattr(api_app, "_SEARCH_LIMIT", 1)
    client = TestClient(app)
    monkeypatch.setattr(api_app.GitHubClient, "search_repositories", lambda *args, **kwargs: [])
    assert client.get("/api/search?q=security").status_code == 200
    response = client.get("/api/search?q=security")
    assert response.status_code == 429
    assert response.headers["Retry-After"].isdigit()
    api_app._search_hits.clear()
    monkeypatch.setattr(api_app, "_SEARCH_LIMIT", 30)


def test_public_github_url_validation_rejects_non_https_and_subdomains():
    from snb.api.app import _public_github_url

    assert _public_github_url("http://github.com/acme/repo") is None
    assert _public_github_url("https://evil.github.com/acme/repo") is None
    assert _public_github_url("https://github.com/acme/repo") == "https://github.com/acme/repo"


def test_openapi_contract_exposes_public_and_private_routes():
    response = TestClient(app).get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/health" in paths
    assert "/api/search" in paths
    assert "/api/graph" in paths
    assert "/api/runs" in paths
    assert "/api/runs/latest" in paths
    assert "/api/runs/{run_id}" in paths
    assert "/api/engineers/{login}" in paths
