"""FastAPI application for the public Security Network Builder API."""

from __future__ import annotations

import os
import re
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from ..github_api import GitHubClient, GitHubError
from ..history import History

app = FastAPI(
    title="Security Network Builder API",
    version="1.0.0",
    description="Public, read-only GitHub security discovery and community graph API.",
)
PUBLIC_PAGE = (Path(__file__).with_name("index.html")).read_text(encoding="utf-8")


@dataclass(frozen=True)
class APISettings:
    """Environment-backed configuration for the public API boundary."""

    history_db: str
    github_token: str | None
    api_key: str | None
    allowed_hosts: tuple[str, ...]


def load_settings() -> APISettings:
    allowed_hosts = tuple(
        host.strip()
        for host in os.environ.get("SNB_ALLOWED_HOSTS", "*").split(",")
        if host.strip()
    )
    return APISettings(
        history_db=os.environ.get("SNB_HISTORY_DB", "data/history.db"),
        github_token=os.environ.get("GITHUB_TOKEN") or None,
        api_key=os.environ.get("API_KEY") or None,
        allowed_hosts=allowed_hosts or ("*",),
    )


app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(load_settings().allowed_hosts))


class HealthResponse(BaseModel):
    status: str
    service: str


class SearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str | None
    description: str | None
    stars: int = Field(ge=0)
    language: str | None
    owner: str | None
    url: str | None


class SearchResponse(BaseModel):
    query: str
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=30)
    results: list[SearchResult]


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    communities: list[Any]


class PublicRepository(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None
    stars: int = Field(ge=0)
    language: str | None
    url: str | None


class PublicEngineerProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    name: str | None
    bio: str | None
    company: str | None
    followers: int = Field(ge=0)
    public_repos: int = Field(ge=0)
    created_at: str | None
    url: str | None
    repositories: list[PublicRepository]


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
    return History(load_settings().history_db)


def require_api_key(value: str | None) -> None:
    configured = load_settings().api_key
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


@app.get("/api/health", response_model=HealthResponse, tags=["public"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="security-network-builder")


@app.get("/api/search", response_model=SearchResponse, tags=["public"])
def search(
    request: Request,
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=30),
    page: int = Query(1, ge=1, le=34),
) -> SearchResponse:
    """Search public GitHub repositories. No private API key is exposed to browsers."""
    _check_search_rate(request)
    client = GitHubClient(load_settings().github_token)
    try:
        items = client.search_repositories(q, per_page=limit, page=page)
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
    return SearchResponse(query=q, page=page, limit=limit, results=results)


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


@app.get("/api/public/engineers/{login}", response_model=PublicEngineerProfile, tags=["public"])
def public_engineer(request: Request, login: str) -> PublicEngineerProfile:
    """Return a sanitized public GitHub engineer profile."""
    _check_search_rate(request)
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
        raise HTTPException(status_code=422, detail="invalid GitHub login")

    client = GitHubClient(load_settings().github_token)
    try:
        profile = client.get_user(login)
        if not profile:
            raise HTTPException(status_code=404, detail="engineer not found")
        repositories = client.list_user_repos(login, limit=12)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    public_repositories = []
    for repo in repositories:
        public_repositories.append(
            PublicRepository(
                name=str(repo.get("name") or ""),
                description=repo.get("description"),
                stars=max(0, int(repo.get("stargazers_count") or 0)),
                language=repo.get("language"),
                url=_public_github_url(repo.get("html_url")),
            )
        )

    return PublicEngineerProfile(
        login=login,
        name=profile.get("name"),
        bio=profile.get("bio"),
        company=profile.get("company"),
        followers=max(0, int(profile.get("followers") or 0)),
        public_repos=max(0, int(profile.get("public_repos") or 0)),
        created_at=profile.get("created_at"),
        url=_public_github_url(profile.get("html_url")),
        repositories=public_repositories,
    )


@app.get("/api/graph", response_model=GraphResponse, tags=["public"])
def graph() -> GraphResponse:
    """Return only the latest run's relationship graph, without triage notes."""
    h = get_history()
    run_id = h.latest_run_id()
    if run_id is None:
        return GraphResponse(nodes=[], edges=[], communities=[])
    data = h.get_run(run_id)
    if not data:
        return GraphResponse(nodes=[], edges=[], communities=[])
    return GraphResponse.model_validate(data.get("graph", {"nodes": [], "edges": [], "communities": []}))
