"""FastAPI application for the public Security Network Builder API."""

from __future__ import annotations

import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse

from ..github_api import GitHubClient, GitHubError
from ..history import History

app = FastAPI(
    title="Security Network Builder API",
    version="1.0.0",
    description="Public, read-only GitHub security discovery and community graph API.",
)
DB_PATH = os.environ.get("SNB_HISTORY_DB", "data/history.db")
PUBLIC_PAGE = (Path(__file__).with_name("index.html")).read_text(encoding="utf-8")

_ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("SNB_ALLOWED_HOSTS", "*").split(",")
    if host.strip()
]
app.add_middleware(TrustedHostMiddleware, allowed_hosts=_ALLOWED_HOSTS or ["*"])


def _public_github_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        return None
    return value


_SEARCH_WINDOW = 60.0
_SEARCH_LIMIT = 30
_search_hits: dict[str, deque[float]] = defaultdict(deque)


def get_history() -> History:
    return History(DB_PATH)


def require_api_key(value: str | None) -> None:
    configured = os.environ.get("API_KEY")
    if configured and (value is None or not secrets.compare_digest(value, configured)):
        raise HTTPException(status_code=401, detail="invalid API key")


def _check_search_rate(request: Request) -> None:
    now = time.monotonic()
    key = request.client.host if request.client else "unknown"
    hits = _search_hits[key]
    while hits and now - hits[0] >= _SEARCH_WINDOW:
        hits.popleft()
    if len(hits) >= _SEARCH_LIMIT:
        retry_after = max(1, int(_SEARCH_WINDOW - (now - hits[0])))
        raise HTTPException(
            status_code=429,
            detail="search rate limit exceeded; try again later",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Any:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
        "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
    )
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(PUBLIC_PAGE)


@app.get("/api/health", tags=["public"])
def health() -> dict[str, str]:
    return {"status": "ok", "service": "security-network-builder"}


@app.get("/api/search", tags=["public"])
def search(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=30),
) -> dict[str, Any]:
    """Search public GitHub repositories. No private API key is exposed to browsers."""
    _check_search_rate(request)
    client = GitHubClient(os.environ.get("GITHUB_TOKEN") or None)
    try:
        items = client.search_repositories(q, per_page=limit)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    results = []
    for item in items:
        owner = item.get("owner") or {}
        results.append(
            {
                "repository": item.get("full_name"),
                "description": item.get("description"),
                "stars": item.get("stargazers_count", 0),
                "language": item.get("language"),
                "owner": owner.get("login"),
                "url": _public_github_url(item.get("html_url")),
            }
        )
    return {"query": q, "results": results}


@app.get("/api/runs", tags=["private"])
def runs(
    limit: int = Query(20, ge=1, le=100),
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    require_api_key(x_api_key)
    return {"runs": get_history().runs(limit)}


@app.get("/api/runs/latest", tags=["private"])
def latest_run(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    h = get_history()
    run_id = h.latest_run_id()
    if run_id is None:
        raise HTTPException(status_code=404, detail="no runs recorded")
    data = h.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="run not found")
    return data


@app.get("/api/runs/{run_id}", tags=["private"])
def get_run(run_id: int, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    data = get_history().get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="run not found")
    return data


@app.get("/api/engineers/{login}", tags=["private"])
def engineer(login: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    return {"login": login, "history": get_history().engineer_history(login)}


@app.get("/api/graph", tags=["public"])
def graph() -> dict[str, Any]:
    """Return only the latest run's relationship graph, without triage notes."""
    h = get_history()
    run_id = h.latest_run_id()
    if run_id is None:
        return {"nodes": [], "edges": [], "communities": []}
    data = h.get_run(run_id)
    if not data:
        return {"nodes": [], "edges": [], "communities": []}
    return data.get("graph", {"nodes": [], "edges": [], "communities": []})
