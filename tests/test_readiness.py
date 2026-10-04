from fastapi.testclient import TestClient
from snb.api.app import app


def test_readiness_fails_closed_without_production_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.delenv("API_KEY", raising=False)
    monkeypatch.delenv("API_KEYS", raising=False)
    response = TestClient(app).get("/api/readiness")
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["authentication"] == "error"


def test_readiness_is_ok_with_production_auth(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.setenv("API_KEYS", "one,two")
    monkeypatch.setenv("SNB_ALLOWED_HOSTS", "example.com")
    response = TestClient(app).get("/api/readiness")
    assert response.json()["status"] == "ok"


def test_readiness_rejects_remote_ai_without_secret(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.setenv("API_KEYS", "one")
    monkeypatch.setenv("SNB_ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("AI_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = TestClient(app).get("/api/readiness")
    assert response.json()["status"] == "degraded"
    assert response.json()["checks"]["ai_provider"] == "error"


def test_readiness_rejects_unknown_ai_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.setenv("API_KEYS", "one")
    monkeypatch.setenv("SNB_ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("AI_PROVIDER", "unknown")
    response = TestClient(app).get("/api/readiness")
    assert response.json()["checks"]["ai_provider"] == "error"
