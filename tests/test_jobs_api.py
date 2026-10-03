from fastapi.testclient import TestClient
from snb.api.app import app

def test_job_api_requires_auth(monkeypatch):
    monkeypatch.setenv("API_KEY", "secret")
    client = TestClient(app)
    assert client.post("/api/jobs?kind=discovery").status_code == 401

def test_job_api_is_idempotent_and_reports_status(monkeypatch, tmp_path):
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    client = TestClient(app)
    headers = {"X-API-Key": "secret", "Idempotency-Key": "scan-1"}
    first = client.post("/api/jobs?kind=discovery", headers=headers)
    second = client.post("/api/jobs?kind=discovery", headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    status = client.get("/api/jobs/" + first.json()["id"], headers={"X-API-Key": "secret"})
    assert status.status_code == 200
    assert status.json()["status"] == "queued"

def test_job_api_rejects_unknown_kind(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    response = TestClient(app).post("/api/jobs?kind=wat")
    assert response.status_code == 422


def test_production_private_api_requires_authentication(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    response = TestClient(app).get("/api/jobs/missing")
    assert response.status_code == 503


def test_job_api_accepts_payload_and_returns_result(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_ENV", "development")
    monkeypatch.setenv("API_KEY", "secret")
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    client = TestClient(app)
    payload = {
        "login": "alice",
        "score": 1,
        "matched_domains": ["Cloud"],
        "breakdown": {"Cloud": 1},
        "evidence": [],
        "repositories": [],
    }
    response = client.post("/api/jobs?kind=intelligence", json=payload,
                           headers={"X-API-Key": "secret", "Idempotency-Key": "alice-1"})
    assert response.status_code == 202
    assert response.json()["result"] == ""
