from fastapi.testclient import TestClient

from snb.api.app import app


def test_versioned_api_root():
    response = TestClient(app).get("/api/v1")
    assert response.status_code == 200
    assert response.json()["current_version"] == "v1"


def test_versioned_health_route():
    response = TestClient(app).get("/api/v1/health")
    assert response.status_code == 200
    assert response.headers["X-API-Version"] == "v1"
    assert response.json()["service"] == "security-network-builder"
