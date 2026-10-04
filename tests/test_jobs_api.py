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


def test_worker_status_requires_auth_and_exposes_only_queue_counts(monkeypatch, tmp_path):
    monkeypatch.setenv("API_KEYS", "secret")
    monkeypatch.setenv("SNB_JOBS_DB", str(tmp_path / "jobs.db"))
    client = TestClient(app)
    assert client.get("/api/worker/status").status_code == 401
    response = client.get("/api/worker/status", headers={"X-API-Key": "secret"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["queue"]) == {"queued", "running", "succeeded", "failed", "total"}


def test_workspace_explanation_is_private_and_records_provenance(monkeypatch, tmp_path):
    from snb.models import Recommendation

    monkeypatch.setenv("API_KEYS", "secret")
    monkeypatch.setenv("SNB_WORKSPACE_DB", str(tmp_path / "workspaces.db"))
    monkeypatch.setenv("AI_PROVIDER", "offline")
    monkeypatch.setattr("snb.api.app.GitHubClient.get_user", lambda self, login: {"login": login, "html_url": f"https://github.com/{login}"})
    monkeypatch.setattr("snb.api.app.GitHubClient.list_user_repos", lambda self, login, limit=30: [{"name": "tool", "stargazers_count": 3, "language": "Go", "description": "security"}])
    monkeypatch.setattr("snb.api.app.score_candidate", lambda *args, **kwargs: Recommendation(
        login="alice", url="https://github.com/alice", score=10, matched_domains=["Cloud"],
        breakdown={"Cloud": 10}, evidence=["repo"], matched_repos=[{"name": "tool", "stars": 3, "language": "Go"}],
    ))
    client = TestClient(app)
    workspace = client.post("/api/workspaces", json={"title": "case"}, headers={"X-API-Key": "secret"}).json()
    response = client.post(
        f"/api/workspaces/{workspace['id']}/explain",
        json={"login": "alice"},
        headers={"X-API-Key": "secret"},
    )
    assert response.status_code == 200
    assert response.json()["source"] == "deterministic"
    assert response.json()["provider"] == "offline"
    data = client.get(f"/api/workspaces/{workspace['id']}", headers={"X-API-Key": "secret"}).json()
    assert any("Explanation (offline):" in note["body"] for note in data["notes"])
