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
