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


def test_readiness_accepts_production_auth_but_requires_postgresql(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.setenv("API_KEYS", "one,two")
    monkeypatch.setenv("SNB_ALLOWED_HOSTS", "example.com")
    monkeypatch.delenv("SNB_DATABASE_URL", raising=False)

    response = TestClient(app).get("/api/readiness")
    body = response.json()

    assert body["status"] == "degraded"
    assert body["checks"]["authentication"] == "ok"
    assert body["checks"]["durable_database"] == "error"


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


def test_readiness_does_not_echo_production_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.setenv("API_KEYS", "super-secret-api-key")
    monkeypatch.setenv("SNB_ALLOWED_HOSTS", "example.com")
    monkeypatch.setenv("AI_PROVIDER", "offline")
    body = TestClient(app).get("/api/readiness").text
    assert "super-secret-api-key" not in body
