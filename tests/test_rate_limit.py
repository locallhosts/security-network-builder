import pytest
from fastapi.testclient import TestClient

from snb.api.app import _PUBLIC_RATE_LIMITER, app
from snb.rate_limit import SlidingWindowLimiter


def test_sliding_window_limiter_expires_and_bounds_clients():
    limiter = SlidingWindowLimiter(max_clients=2)
    assert limiter.check("a", limit=2, window=60, now=0).allowed
    assert limiter.check("a", limit=2, window=60, now=1).allowed
    blocked = limiter.check("a", limit=2, window=60, now=2)
    assert not blocked.allowed
    assert blocked.retry_after >= 58
    assert limiter.check("a", limit=2, window=60, now=61).allowed
    limiter.check("b", limit=1, window=60, now=62)
    limiter.check("c", limit=1, window=60, now=63)
    assert len(limiter._hits) <= 2


def test_public_search_returns_429_with_retry_after(monkeypatch):
    monkeypatch.setenv("SNB_RATE_LIMIT_SEARCH", "2")
    _PUBLIC_RATE_LIMITER.reset()
    monkeypatch.setattr(
        "snb.api.app.GitHubClient.search_repositories",
        lambda self, query, per_page=30, page=1, sort="stars": [],
    )
    client = TestClient(app)
    assert client.get("/api/search?q=security").status_code == 200
    second = client.get("/api/search?q=security")
    assert second.status_code == 200
    blocked = client.get("/api/search?q=security")
    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.json()["detail"]["error"] == "rate_limit_exceeded"
    assert blocked.headers["X-RateLimit-Limit"] == "2"
    _PUBLIC_RATE_LIMITER.reset()


def test_public_rate_limits_are_endpoint_specific(monkeypatch):
    monkeypatch.setenv("SNB_RATE_LIMIT_SEARCH", "1")
    monkeypatch.setenv("SNB_RATE_LIMIT_USERS_SEARCH", "1")
    _PUBLIC_RATE_LIMITER.reset()
    monkeypatch.setattr("snb.api.app.GitHubClient.search_repositories", lambda *args, **kwargs: [])
    monkeypatch.setattr("snb.api.app.GitHubClient.search_users", lambda *args, **kwargs: [])
    client = TestClient(app)
    assert client.get("/api/search?q=security").status_code == 200
    assert client.get("/api/users/search?q=security").status_code == 200
    assert client.get("/api/search?q=security").status_code == 429
    _PUBLIC_RATE_LIMITER.reset()


def test_security_headers_and_correlation_id_are_present():
    response = TestClient(app).get("/api/health", headers={"X-Request-ID": "phase4-test-01"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "phase4-test-01"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_request_size_guard_rejects_oversized_body():
    client = TestClient(app)
    response = client.post(
        "/api/workspaces",
        headers={"Content-Length": str(2 * 1024 * 1024)},
        content=b"{}",
    )
    assert response.status_code == 413
