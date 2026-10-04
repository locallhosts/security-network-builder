from snb.readiness import readiness


def test_production_requires_postgresql(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.setenv("API_KEYS", "test-key")
    monkeypatch.setenv("SNB_ALLOWED_HOSTS", "example.onrender.com")
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    monkeypatch.delenv("SNB_DATABASE_URL", raising=False)

    result = readiness()
    assert result["checks"]["durable_database"] == "error"
    assert result["status"] == "degraded"


def test_production_accepts_postgresql(monkeypatch, tmp_path):
    monkeypatch.setenv("SNB_ENV", "production")
    monkeypatch.setenv("API_KEYS", "test-key")
    monkeypatch.setenv("SNB_ALLOWED_HOSTS", "example.onrender.com")
    monkeypatch.setenv("SNB_HISTORY_DB", str(tmp_path / "history.db"))
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    monkeypatch.setenv("SNB_DATABASE_URL", "postgresql://example.invalid/db")

    result = readiness()
    assert result["checks"]["durable_database"] == "ok"
