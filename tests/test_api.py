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
    client = TestClient(app)
    assert client.get("/api/search?q=ebpf").status_code != 401


def test_graph_is_public_even_when_api_key_is_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = TestClient(app)
    assert client.get("/api/graph").status_code == 200
