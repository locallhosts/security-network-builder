from fastapi.testclient import TestClient
from snb.api.app import app

def test_watchlist_api_is_private_and_bounded(monkeypatch, tmp_path):
    monkeypatch.setenv("API_KEYS", "secret")
    monkeypatch.setenv("SNB_WATCHLIST_DB", str(tmp_path / "watchlists.db"))
    client = TestClient(app)
    assert client.get("/api/watchlists").status_code == 401
    response = client.post(
        "/api/watchlists",
        json={"name": "Cloud", "query": "cloud security", "interval_minutes": 60, "domains": ["cloud"]},
        headers={"X-API-Key": "secret"},
    )
    assert response.status_code == 201
    item = response.json()
    assert item["interval_minutes"] == 60
    listed = client.get("/api/watchlists", headers={"X-API-Key": "secret"})
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == item["id"]

def test_alert_api_is_private(monkeypatch, tmp_path):
    monkeypatch.setenv("API_KEYS", "secret")
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    client = TestClient(app)
    assert client.get("/api/alerts").status_code == 401
    response = client.get("/api/alerts", headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    assert response.json()["alerts"] == []
