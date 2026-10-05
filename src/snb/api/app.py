"""FastAPI application for the public Security Network Builder API."""

from __future__ import annotations

import os
import re
import json
import logging
from datetime import datetime, timezone
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from fastapi import Body, FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html, get_swagger_ui_oauth2_redirect_html
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..audit import AuditLog
from ..config import Profile
from ..github_api import GitHubClient, GitHubError
from ..history import History
from ..search_history import SearchHistoryStore
from ..jobs import JobQueue
from ..intelligence import IntelligenceError, build_provider
from ..readiness import readiness
from ..workspace import WorkspaceStore
from ..scoring import score_candidate
from ..rate_limit import SlidingWindowLimiter
from ..alerts import changes_since_previous_run
from ..alert_state import AlertStore
from ..watchlists import WatchlistStore
from ..public_sources import fetch_cisa_kev
from ..main import analyse, enrich_rest
from ..graph import build_graph
from ..models import Candidate, Recommendation
from ..organization_intelligence import analyze_organization_intelligence

app = FastAPI(
    title="Security Network Builder API",
    version="1.0.0",
    description="Public GitHub security discovery, engineer intelligence, and community graph API.",
    docs_url=None,
    redoc_url=None,
)
PUBLIC_PAGE = (Path(__file__).with_name("index.html")).read_text(encoding="utf-8")

# FastAPI disables its automatic documentation routes because the application
# uses a strict, explicit security-header policy.  Re-enable the interactive
# documentation with the same generated OpenAPI schema and a docs-specific CSP.
@app.get("/docs", include_in_schema=False)
async def swagger_ui_html() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get("/docs/oauth2-redirect", include_in_schema=False)
async def swagger_ui_redirect() -> HTMLResponse:
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False)
async def redoc_html() -> HTMLResponse:
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js",
    )




@dataclass(frozen=True)
class APISettings:
    """Environment-backed configuration for the public API boundary."""

    history_db: str
    github_token: str | None
    api_keys: tuple[str, ...]
    environment: str
    allowed_hosts: tuple[str, ...]
    jobs_db: str

    @property
    def api_key(self) -> str | None:
        """Backward-compatible single-key view for callers and older integrations."""
        return self.api_keys[0] if self.api_keys else None


def load_settings() -> APISettings:
    allowed_hosts = tuple(
        host.strip()
        for host in os.environ.get("SNB_ALLOWED_HOSTS", "*").split(",")
        if host.strip()
    )
    return APISettings(
        history_db=os.environ.get("SNB_HISTORY_DB", "data/history.db"),
        github_token=os.environ.get("GITHUB_TOKEN") or None,
        api_keys=tuple(k.strip() for k in os.environ.get("API_KEYS", os.environ.get("API_KEY", "")).split(",") if k.strip()),
        environment=os.environ.get("SNB_ENV", "development").strip().lower(),
        allowed_hosts=allowed_hosts or ("*",),
        jobs_db=os.environ.get("SNB_JOBS_DB", "data/jobs.db"),
    )


app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(load_settings().allowed_hosts))
_cors_origins = tuple(o.strip() for o in os.environ.get("SNB_CORS_ORIGINS", "").split(",") if o.strip())
if _cors_origins:
    app.add_middleware(CORSMiddleware, allow_origins=list(_cors_origins), allow_credentials=False, allow_methods=["GET", "HEAD", "OPTIONS"], allow_headers=["Accept", "Content-Type", "X-Request-ID", "X-API-Key"], max_age=600)


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
    source: str = "github"
    generated_at: str

class PublicGraphBuildRequest(BaseModel):
    query: str = Field(min_length=2, max_length=100)
    limit: int = Field(default=20, ge=1, le=30)
    top: int = Field(default=15, ge=1, le=25)
    min_score: float = Field(default=0, ge=0, le=1000)
    language: str | None = Field(default=None, max_length=40)
    min_stars: int = Field(default=0, ge=0, le=1_000_000)
    owner: str | None = Field(default=None, max_length=39, pattern="^[A-Za-z0-9-]+$")
    topic: str | None = Field(default=None, max_length=50)
    archived: bool | None = None
    fork: bool | None = None
    sort: str = Field(default="stars", pattern="^(stars|forks|updated|help-wanted-issues|best-match)$")


class UserSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    login: str
    name: str | None
    avatar_url: str | None
    followers: int = Field(ge=0)
    public_repos: int = Field(ge=0)
    type: str
    url: str | None


class UserSearchResponse(BaseModel):
    query: str
    page: int = Field(ge=1)
    limit: int = Field(ge=1, le=30)
    results: list[UserSearchResult]
    source: str = "github"
    generated_at: str


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    communities: list[Any]
    generated_at: str | None = None
    snapshot_created_at: str | None = None
    run_id: int | None = None
    source: str = "snb-analysis"
    filters: dict[str, Any] = Field(default_factory=dict)


class PublicRepository(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None
    stars: int = Field(ge=0)
    language: str | None
    url: str | None


class WorkspaceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class WorkspaceUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|reviewing|closed)$")
    tags: list[str] | None = Field(default=None, max_length=30)


class WorkspaceItem(BaseModel):
    kind: str = Field(pattern="^(engineer|repository)$")
    value: str = Field(min_length=1, max_length=200)
    label: str | None = Field(default=None, max_length=200)
    source_url: str | None = Field(default=None, max_length=500)


class WorkspaceNote(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    source_url: str | None = Field(default=None, max_length=500)


class WorkspaceExplain(BaseModel):
    login: str = Field(min_length=1, max_length=39, pattern="^[A-Za-z0-9-]+$")


class SearchHistoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    query: str = Field(min_length=2, max_length=100)
    limit: int = Field(default=30, ge=1, le=30)
    sort: str = Field(default="stars", pattern="^(stars|forks|help-wanted-issues|updated)$")


class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    attempts: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    last_error: str
    result: str


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
    organizations: list[str]
    activity: list[dict[str, str | None]]
    security_domains: list[str]
    skills: list[str]
    contribution_trends: dict[str, int]
    repository_signals: list[dict[str, Any]]
    score: float | None
    matched_domains: list[str]
    score_breakdown: dict[str, float]
    evidence: list[str]


def _nonnegative_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


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


def _parse_github_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _public_engineer_intelligence(repositories: list[dict[str, Any]]) -> tuple[list[str], list[str], dict[str, int], list[dict[str, Any]]]:
    """Derive deterministic, public-data-only intelligence from repository metadata."""
    profile = Profile.load()
    domain_hits: dict[str, set[str]] = {}
    skills: set[str] = set()
    trends = {"last_30_days": 0, "last_90_days": 0, "last_365_days": 0}
    signals: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    for repo in repositories:
        hits = profile.match_repo(repo)
        for key in hits:
            domain = next((d for d in profile.domains if d.key == key), None)
            if domain:
                domain_hits.setdefault(domain.label, set()).update(hits[key])

        language = repo.get("language")
        if isinstance(language, str) and language.strip():
            skills.add(language.strip())
        for keyword_set in hits.values():
            skills.update(keyword_set)

        pushed = _parse_github_timestamp(repo.get("pushed_at"))
        age_days = None if pushed is None else max(0, (now - pushed).days)
        if age_days is not None:
            if age_days <= 30:
                trends["last_30_days"] += 1
            if age_days <= 90:
                trends["last_90_days"] += 1
            if age_days <= 365:
                trends["last_365_days"] += 1

        archived = bool(repo.get("archived", False))
        fork = bool(repo.get("fork", False))
        if archived:
            maintenance = "archived"
        elif age_days is None:
            maintenance = "unknown"
        elif age_days <= 90:
            maintenance = "active"
        elif age_days <= 365:
            maintenance = "stale"
        else:
            maintenance = "inactive"

        signals.append({
            "name": str(repo.get("name") or ""),
            "stars": _nonnegative_int(repo.get("stargazers_count")),
            "forks": _nonnegative_int(repo.get("forks_count")),
            "open_issues": _nonnegative_int(repo.get("open_issues_count")),
            "archived": archived,
            "fork": fork,
            "pushed_at": repo.get("pushed_at"),
            "maintenance": maintenance,
            "security_domains": sorted(
                next((d.label for d in profile.domains if d.key == key), key)
                for key in hits
            ),
        })

    signals.sort(key=lambda item: (-item["stars"], item["name"].lower()))
    return sorted(domain_hits), sorted(skills, key=str.lower)[:40], trends, signals[:30]


def analyze_organization_intelligence(recs: list[Any]) -> list[dict[str, Any]]:
    """Summarize organization evidence from the current recommendation set.

    The public graph endpoint must work from the same bounded search result
    that produced the graph.  This deterministic summary intentionally uses
    only organization/login/score data already present in each recommendation.
    """
    organizations: dict[str, dict[str, Any]] = {}
    for rec in recs:
        score = float(getattr(rec, "score", 0.0) or 0.0)
        login = str(getattr(rec, "login", "") or "")
        for org in getattr(rec, "orgs", []) or []:
            if not isinstance(org, str) or not org.strip():
                continue
            key = org.strip()
            entry = organizations.setdefault(
                key,
                {"organization": key, "engineers": [], "engineer_count": 0, "max_score": 0.0},
            )
            if login and login not in entry["engineers"]:
                entry["engineers"].append(login)
            entry["max_score"] = max(entry["max_score"], score)

    result = []
    for entry in organizations.values():
        entry["engineers"].sort()
        entry["engineer_count"] = len(entry["engineers"])
        result.append(entry)
    return sorted(result, key=lambda x: (-x["engineer_count"], -x["max_score"], x["organization"].lower()))


_METRICS = {"requests": 0, "errors": 0, "rate_limited": 0, "github_errors": 0, "searches": 0, "profiles": 0, "graphs": 0}


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps({"timestamp": datetime.now(timezone.utc).isoformat(), "level": record.levelname, "message": record.getMessage(), "logger": record.name})


log = logging.getLogger("snb.api")


_PUBLIC_RATE_LIMITER = SlidingWindowLimiter(max_clients=5000)
_PUBLIC_RATE_LIMITS: dict[str, tuple[int, float]] = {
    "search": (30, 60.0),
    "users_search": (30, 60.0),
    "profile": (60, 60.0),
    "compare": (20, 60.0),
    "relationships": (30, 60.0),
    "graph": (20, 60.0),
    "graph_search": (30, 60.0),
    "graph_build": (3, 600.0),
    "usage": (10, 60.0),
    "kev": (10, 60.0),
}
_PUBLIC_PATHS = {"/api/search", "/api/users/search", "/api/graph", "/api/public/graph/build", "/api/usage"}
_PRIVATE_BODY_LIMIT = 1_048_576
_PUBLIC_BODY_LIMIT = 32_768


def _env_limit(name: str, default: tuple[int, float]) -> tuple[int, float]:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = max(1, int(raw))
    except ValueError:
        return default
    return value, default[1]


def _public_client_key(request: Request, endpoint: str) -> str:
    host = request.client.host if request.client else "unknown"
    return f"{host}:{endpoint}"


def _check_public_rate(request: Request, endpoint: str, response: Response | None = None) -> None:
    limit, window = _env_limit(f"SNB_RATE_LIMIT_{endpoint.upper()}", _PUBLIC_RATE_LIMITS[endpoint])
    decision = _PUBLIC_RATE_LIMITER.check(_public_client_key(request, endpoint), limit=limit, window=window)
    request.state.rate_limit = decision
    if response is not None:
        response.headers["X-RateLimit-Limit"] = str(decision.limit)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        response.headers["X-RateLimit-Reset"] = str(decision.reset_after)
    if not decision.allowed:
        _METRICS["rate_limited"] += 1
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "message": "too many requests", "retry_after": decision.retry_after},
            headers={"Retry-After": str(decision.retry_after)},
        )


def get_history() -> History:
    settings = load_settings()
    return History(settings.history_db, database_url=os.environ.get("SNB_DATABASE_URL"))


def get_jobs() -> JobQueue:
    return JobQueue(load_settings().jobs_db)


def get_workspaces() -> WorkspaceStore:
    return WorkspaceStore(os.environ.get("SNB_WORKSPACE_DB", "data/workspaces.db"))


def require_api_key(value: str | None) -> None:
    settings = load_settings()
    audit = AuditLog(os.environ.get("SNB_AUDIT_DB", "data/audit.db"))
    if not settings.api_keys:
        if settings.environment == "production":
            audit.record("auth.private", outcome="rejected", detail="production authentication not configured")
            raise HTTPException(status_code=503, detail="private API authentication is not configured")
        return
    if value is None or not any(secrets.compare_digest(value, configured) for configured in settings.api_keys):
        audit.record("auth.private", outcome="rejected", detail="invalid API key")
        raise HTTPException(status_code=401, detail="invalid API key")


@app.middleware("http")
async def api_version_router(request: Request, call_next: Any) -> Any:
    """Route stable /api/v1 URLs to the current public API implementation.

    The versioned prefix is deliberately explicit; unversioned /api URLs remain
    compatibility aliases during the current release line.
    """
    path = request.scope.get("path", "")
    if path == "/api/v1" or path.startswith("/api/v1/"):
        rewritten = "/api" + path[len("/api/v1"):]
        request.scope["path"] = rewritten or "/api"
        request.scope["raw_path"] = rewritten.encode("utf-8")
        request.state.api_version = "v1"
    else:
        request.state.api_version = "legacy"
    response = await call_next(request)
    response.headers.setdefault("X-API-Version", getattr(request.state, "api_version", "legacy"))
    return response


@app.middleware("http")
async def request_size_guard(request: Request, call_next: Any) -> Any:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            declared = int(content_length)
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "invalid content length"})
        limit = _PUBLIC_BODY_LIMIT if request.url.path in _PUBLIC_PATHS else _PRIVATE_BODY_LIMIT
        if declared > limit:
            return JSONResponse(status_code=413, content={"detail": "request body too large"})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next: Any) -> Any:
    supplied_id = request.headers.get("X-Request-ID")
    correlation_id = supplied_id if supplied_id and re.fullmatch(r"[A-Za-z0-9._:-]{1,128}", supplied_id) else secrets.token_hex(12)
    request.state.correlation_id = correlation_id
    _METRICS["requests"] += 1
    started = time.monotonic()
    try:
        response = await call_next(request)
    except Exception:
        _METRICS["errors"] += 1
        log.exception("request_failed")
        raise
    finally:
        log.info("request %s %s correlation_id=%s duration_ms=%.1f", request.method, request.url.path, correlation_id, (time.monotonic() - started) * 1000)
    response.headers.setdefault("X-Request-ID", correlation_id)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path in {"/docs", "/redoc"}:
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; connect-src 'self'; "
            "img-src 'self' data: https://fastapi.tiangolo.com; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
    else:
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
        )
    if hasattr(request.state, "rate_limit"):
        decision = request.state.rate_limit
        response.headers.setdefault("X-RateLimit-Limit", str(decision.limit))
        response.headers.setdefault("X-RateLimit-Remaining", str(decision.remaining))
        response.headers.setdefault("X-RateLimit-Reset", str(decision.reset_after))
    if request.url.path.startswith("/api/"):
        public_cache = request.url.path in {"/api/search", "/api/users/search", "/api/public/engineers/compare", "/api/graph"}
        response.headers.setdefault("Cache-Control", "public, max-age=30, stale-while-revalidate=60" if public_cache else "no-store")
    return response


@app.get("/docs", include_in_schema=False, response_class=HTMLResponse)
def swagger_docs() -> HTMLResponse:
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - Swagger UI",
        oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get(app.swagger_ui_oauth2_redirect_url, include_in_schema=False)
def swagger_redirect() -> HTMLResponse:
    return get_swagger_ui_oauth2_redirect_html()


@app.get("/redoc", include_in_schema=False, response_class=HTMLResponse)
def redoc_docs() -> HTMLResponse:
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=app.title + " - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2/bundles/redoc.standalone.js",
    )


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return HTMLResponse(PUBLIC_PAGE)


@app.get("/api/readiness", tags=["public"])
def readiness_endpoint() -> dict[str, Any]:
    return readiness()


@app.get("/api", tags=["public"])
def api_info() -> dict[str, Any]:
    return {
        "service": "security-network-builder",
        "current_version": "v1",
        "versions": {"v1": "/api/v1"},
        "legacy_alias": "/api",
    }


@app.get("/api/health", response_model=HealthResponse, tags=["public"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="security-network-builder")


@app.get("/api/search", response_model=SearchResponse, tags=["public"])
def search(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=30),
    page: int = Query(1, ge=1, le=34),
    language: str | None = Query(default=None, max_length=40),
    min_stars: int = Query(0, ge=0, le=1_000_000),
    sort: str = Query("stars", pattern="^(stars|forks|updated|help-wanted-issues|best-match)$"),
    owner: str | None = Query(default=None, max_length=39, pattern="^[A-Za-z0-9-]+$"),
    topic: str | None = Query(default=None, max_length=50),
    archived: bool | None = Query(default=None),
    fork: bool | None = Query(default=None),
) -> SearchResponse:
    """Search public GitHub repositories. No private API key is exposed to browsers."""
    _check_public_rate(request, "search", response)
    _METRICS["searches"] += 1
    client = GitHubClient(load_settings().github_token)
    search_query = q.strip()
    if language:
        search_query += f" language:{language.strip()}"
    if min_stars:
        search_query += f" stars:>={min_stars}"
    if owner:
        search_query += f" user:{owner}"
    if topic:
        search_query += f" topic:{topic.strip()}"
    if archived is not None:
        search_query += f" archived:{str(archived).lower()}"
    if fork is not None:
        search_query += f" fork:{str(fork).lower()}"
    try:
        items = client.search_repositories(search_query, per_page=limit, page=page, sort=sort)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail="upstream unavailable") from exc
    results = []
    seen: set[str] = set()
    for item in items:
        owner = item.get("owner") or {}
        full_name = item.get("full_name")
        if not isinstance(full_name, str) or full_name.lower() in seen:
            continue
        seen.add(full_name.lower())
        raw = {
            "repository": item.get("full_name"),
            "description": item.get("description"),
            "stars": item.get("stargazers_count", 0),
            "language": item.get("language"),
            "owner": owner.get("login"),
            "url": _public_github_url(item.get("html_url")),
        }
        try:
            results.append(SearchResult.model_validate(raw))
        except ValidationError as exc:
            raise HTTPException(status_code=500, detail="invalid upstream search result") from exc
    if response is not None:
        for header in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"):
            if header in client.last_headers:
                response.headers[header] = client.last_headers[header]
        response.headers["X-Data-Source"] = "github"
    return SearchResponse(query=q, page=page, limit=limit, results=results, generated_at=datetime.now(timezone.utc).isoformat())


@app.get("/api/graph/search", tags=["public"])
def graph_search(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    """Search the latest persisted SNB intelligence snapshot without changing it."""
    _check_public_rate(request, "graph_search", response)
    h = get_history()
    run_id = h.latest_run_id()
    if run_id is None:
        return {"query": q, "run_id": None, "results": [], "source": "snb-analysis"}

    data = h.get_run(run_id)
    if not data:
        return {"query": q, "run_id": run_id, "results": [], "source": "snb-analysis"}

    needle = q.strip().lower()
    graph_data = data.get("graph") or {}
    nodes = {str(n.get("login")): n for n in graph_data.get("nodes", []) if n.get("login")}
    matches: list[dict[str, Any]] = []
    for raw in data.get("recommendations", []):
        login = str(raw.get("login") or "")
        if not login:
            continue
        searchable = " ".join(
            [
                login,
                " ".join(str(x) for x in raw.get("matched_domains", [])),
                " ".join(str(x) for x in raw.get("orgs", [])),
                " ".join(str(x) for x in raw.get("evidence", [])),
                " ".join(str((x or {}).get("name", "")) for x in raw.get("matched_repos", [])),
            ]
        ).lower()
        if needle not in searchable:
            continue
        node = nodes.get(login, {})
        matches.append(
            {
                "login": login,
                "score": raw.get("score", 0),
                "matched_domains": raw.get("matched_domains", []),
                "orgs": raw.get("orgs", []),
                "evidence": raw.get("evidence", [])[:5],
                "community": node.get("community"),
                "centrality": node.get("centrality", 0),
                "url": raw.get("url"),
            }
        )
    matches.sort(key=lambda x: (-float(x.get("score", 0)), str(x.get("login", "")).lower()))
    return {
        "query": q,
        "run_id": run_id,
        "source": "snb-analysis",
        "results": matches[:limit],
    }


@app.post("/api/public/graph/build", tags=["public"])
def build_public_graph(payload: PublicGraphBuildRequest, request: Request, response: Response) -> dict[str, Any]:
    """Build and persist a bounded graph from the user's current public GitHub search."""
    _check_public_rate(request, "graph_build", response)
    profile = Profile.load()
    client = GitHubClient(load_settings().github_token)
    search_query = payload.query.strip()
    if payload.language:
        search_query += f" language:{payload.language.strip()}"
    if payload.min_stars:
        search_query += f" stars:>={payload.min_stars}"
    if payload.owner:
        search_query += f" user:{payload.owner}"
    if payload.topic:
        search_query += f" topic:{payload.topic.strip()}"
    if payload.archived is not None:
        search_query += f" archived:{str(payload.archived).lower()}"
    if payload.fork is not None:
        search_query += f" fork:{str(payload.fork).lower()}"
    try:
        items = client.search_repositories(search_query, per_page=payload.limit, page=1, sort=payload.sort)
    except GitHubError as exc:
        _METRICS["github_errors"] += 1
        raise HTTPException(status_code=502, detail="upstream GitHub service unavailable") from exc

    excluded = {u.lower() for u in profile.settings.exclude_users}
    if profile.github_username:
        excluded.add(profile.github_username.lower())
    candidates: dict[str, Candidate] = {}
    for item in items:
        owner_data = item.get("owner") or {}
        login = owner_data.get("login")
        if not isinstance(login, str) or not login or login.lower() in excluded:
            continue
        if profile.settings.users_only and owner_data.get("type") != "User":
            continue
        candidate = candidates.setdefault(
            login,
            Candidate(login=login, html_url=owner_data.get("html_url", f"https://github.com/{login}")),
        )
        candidate.seed_repos.append(item)

    ranked = sorted(candidates.values(), key=lambda c: c.seed_weight, reverse=True)
    recs = analyse(client, ranked, profile, "rest", payload.min_score)
    recs.sort(key=lambda r: r.score, reverse=True)
    recs = recs[: payload.top]
    if recs:
        enrich_rest(client, recs)
        recs.sort(key=lambda r: r.score, reverse=True)

    if not recs:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "no_engineers_matched",
                "message": "The current GitHub search produced candidates, but SNB analysis returned no engineers. Try a broader query, lower the minimum score, or adjust the filters.",
                "candidates": len(candidates),
            },
        )

    graph = build_graph(recs).to_dict()
    org_summary = analyze_organization_intelligence(recs)
    run_id = None
    if recs:
        run_id = get_history().save_run(recs, profile.name, "rest-web", graph, org_summary)
    _METRICS["graphs"] += 1
    return {
        "schema_version": 1,
        "source": "github-search",
        "query": payload.query,
        "search_query": search_query,
        "candidates": len(candidates),
        "engineers": len(recs),
        "run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "graph": graph,
    }


@app.post("/api/jobs", response_model=JobResponse, status_code=202, tags=["private"])
def enqueue_job(
    kind: str = Query(..., min_length=1, max_length=100),
    payload: dict[str, Any] = Body(default_factory=dict),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_api_key: str | None = Header(default=None),
) -> JobResponse:
    require_api_key(x_api_key)
    if kind not in {"discovery", "intelligence"}:
        raise HTTPException(status_code=422, detail="unsupported job kind")
    try:
        job = get_jobs().enqueue(kind, payload, idempotency_key=idempotency_key)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return JobResponse(id=job.id, kind=job.kind, status=job.status, attempts=job.attempts,
                       max_attempts=job.max_attempts, last_error=job.last_error, result=job.result)


@app.get("/api/worker/status", tags=["private"])
def worker_status(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    """Return queue health without exposing job payloads or private results."""
    require_api_key(x_api_key)
    try:
        stats = get_jobs().stats()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="worker queue unavailable") from exc
    return {"status": "ok", "queue": stats, "provider": os.environ.get("AI_PROVIDER", "offline").strip().lower()}

@app.get("/api/jobs/{job_id}", response_model=JobResponse, tags=["private"])
def job_status(job_id: str, x_api_key: str | None = Header(default=None)) -> JobResponse:
    require_api_key(x_api_key)
    try:
        job = get_jobs().get(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    return JobResponse(id=job.id, kind=job.kind, status=job.status, attempts=job.attempts,
                       max_attempts=job.max_attempts, last_error=job.last_error, result=job.result)


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


@app.get("/api/engineers/{login}/analysis", tags=["private"])
def engineer_analysis(login: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    """Return the explainable security score for one engineer plus stored history."""
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
        raise HTTPException(status_code=422, detail="invalid GitHub login")
    require_api_key(x_api_key)

    client = GitHubClient(load_settings().github_token)
    try:
        profile_data = client.get_user(login)
        if not profile_data:
            raise HTTPException(status_code=404, detail="engineer not found")
        repos = client.list_user_repos(login, limit=100)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail="upstream GitHub service unavailable") from exc

    recommendation = score_candidate(login, repos, Profile.load())
    history = get_history().engineer_history(login)
    if recommendation is None:
        return {
            "login": login,
            "score": None,
            "matched_domains": [],
            "breakdown": {},
            "evidence": [],
            "matched_repositories": [],
            "history": history,
        }

    return {
        "login": recommendation.login,
        "score": recommendation.score,
        "matched_domains": recommendation.matched_domains,
        "breakdown": recommendation.breakdown,
        "evidence": recommendation.evidence,
        "matched_repositories": recommendation.matched_repos,
        "history": history,
    }


@app.get("/api/users/search", response_model=UserSearchResponse, tags=["public"])
def search_users(
    request: Request,
    response: Response,
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=30),
    page: int = Query(1, ge=1, le=34),
    sort: str = Query("followers", pattern="^(followers|repositories|joined)$"),
) -> UserSearchResponse:
    """Search public GitHub users without exposing credentials to the browser."""
    _check_public_rate(request, "users_search", response)
    client = GitHubClient(load_settings().github_token)
    try:
        items = client.search_users(q.strip(), per_page=limit, page=page, sort=sort)
    except GitHubError as exc:
        _METRICS["github_errors"] += 1
        raise HTTPException(status_code=502, detail="upstream GitHub service unavailable") from exc

    results = []
    for item in items:
        login = str(item.get("login") or "")
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
            continue
        avatar = item.get("avatar_url")
        results.append(
            UserSearchResult(
                login=login,
                name=None,
                avatar_url=avatar if isinstance(avatar, str) and avatar.startswith("https://avatars.githubusercontent.com/") else None,
                followers=_nonnegative_int(item.get("followers")),
                public_repos=_nonnegative_int(item.get("public_repos")),
                type=str(item.get("type") or "User"),
                url=_public_github_url(item.get("html_url")),
            )
        )
    return UserSearchResponse(query=q, page=page, limit=limit, results=results, generated_at=datetime.now(timezone.utc).isoformat())


@app.get("/api/public/engineers/compare", tags=["public"])
def compare_engineers(
    request: Request,
    response: Response,
    first: str = Query(..., min_length=1, max_length=39, pattern="^[A-Za-z0-9-]+$"),
    second: str = Query(..., min_length=1, max_length=39, pattern="^[A-Za-z0-9-]+$"),
) -> dict[str, Any]:
    _check_public_rate(request, "compare", response)
    if first.lower() == second.lower():
        raise HTTPException(status_code=422, detail="compare two different engineers")
    client = GitHubClient(load_settings().github_token)
    profiles = []
    for login in (first, second):
        try:
            profile = client.get_user(login)
            repos = client.list_user_repos(login, limit=30)
        except GitHubError as exc:
            _METRICS["github_errors"] += 1
            raise HTTPException(status_code=502, detail="upstream unavailable") from exc
        if not profile:
            raise HTTPException(status_code=404, detail=f"engineer not found: {login}")
        domains, skills, trends, signals = _public_engineer_intelligence(repos)
        rec = score_candidate(login, repos, Profile.load())
        profiles.append({
            "login": login,
            "name": profile.get("name"),
            "score": None if rec is None else rec.score,
            "domains": domains,
            "skills": skills,
            "trends": trends,
            "repository_count": len(repos),
            "top_repositories": signals[:10],
        })
    return {"schema_version": 1, "source": "github", "profiles": profiles}




@app.get("/api/public/engineers/{login}", response_model=PublicEngineerProfile, tags=["public"])
def public_engineer(request: Request, response: Response, login: str) -> PublicEngineerProfile:
    """Return a sanitized public GitHub engineer profile."""
    _check_public_rate(request, "profile", response)
    _METRICS["profiles"] += 1
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
        raise HTTPException(status_code=422, detail="invalid GitHub login")

    client = GitHubClient(load_settings().github_token)
    try:
        profile = client.get_user(login)
        if not profile:
            raise HTTPException(status_code=404, detail="engineer not found")
        repositories = client.list_user_repos(login, limit=30)
        organizations = client.list_user_orgs(login)
    except GitHubError as exc:
        _METRICS["github_errors"] += 1
        raise HTTPException(status_code=502, detail="upstream GitHub service unavailable") from exc

    public_repositories = []
    activity = []
    for repo in repositories:
        public_repositories.append(
            PublicRepository(
                name=str(repo.get("name") or ""),
                description=repo.get("description"),
                stars=_nonnegative_int(repo.get("stargazers_count")),
                language=repo.get("language"),
                url=_public_github_url(repo.get("html_url")),
            )
        )
        activity.append(
            {
                "repository": str(repo.get("name") or ""),
                "pushed_at": repo.get("pushed_at"),
                "language": repo.get("language"),
            }
        )

    domains, skills, trends, repository_signals = _public_engineer_intelligence(repositories)
    recommendation = score_candidate(login, repositories, Profile.load())
    score = None if recommendation is None else recommendation.score
    matched_domains = [] if recommendation is None else recommendation.matched_domains
    score_breakdown = {} if recommendation is None else recommendation.breakdown
    evidence = [] if recommendation is None else recommendation.evidence
    return PublicEngineerProfile(
        login=login,
        name=profile.get("name"),
        bio=profile.get("bio"),
        company=profile.get("company"),
        followers=_nonnegative_int(profile.get("followers")),
        public_repos=_nonnegative_int(profile.get("public_repos")),
        created_at=profile.get("created_at"),
        url=_public_github_url(profile.get("html_url")),
        repositories=public_repositories,
        organizations=sorted(set(organizations)),
        activity=activity,
        security_domains=domains,
        skills=skills,
        contribution_trends=trends,
        repository_signals=repository_signals,
        score=score,
        matched_domains=matched_domains,
        score_breakdown=score_breakdown,
        evidence=evidence,
    )


@app.get("/api/public/threats/kev", tags=["public"])
def kev_catalog(
    request: Request,
    response: Response,
    limit: int = Query(25, ge=1, le=100),
) -> dict[str, Any]:
    """Return a bounded snapshot from the public CISA Known Exploited Vulnerabilities catalog."""
    _check_public_rate(request, "kev", response)
    try:
        return fetch_cisa_kev(limit=limit)
    except Exception as exc:
        _METRICS["errors"] += 1
        raise HTTPException(status_code=502, detail="public threat source unavailable") from exc


@app.get("/api/metrics", tags=["public"])
def metrics() -> dict[str, Any]:
    return {"service": "security-network-builder", "metrics": dict(_METRICS), "generated_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/usage", tags=["public"])
def usage(request: Request, response: Response) -> dict[str, Any]:
    _check_public_rate(request, "usage", response)
    client = GitHubClient(load_settings().github_token)
    try:
        resources = client.rate_limit()
    except GitHubError as exc:
        _METRICS["github_errors"] += 1
        raise HTTPException(status_code=502, detail="upstream GitHub service unavailable") from exc
    response.headers["X-Data-Source"] = "github"
    return {"source": "github", "core": resources.get("core") or {}, "search": resources.get("search") or {}, "generated_at": datetime.now(timezone.utc).isoformat()}




@app.post("/api/search-history", status_code=201, tags=["private"])
def create_search_history(
    payload: SearchHistoryCreate,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    """Run a bounded public GitHub repository search and persist its snapshot locally."""
    require_api_key(x_api_key)
    client = GitHubClient(load_settings().github_token)
    try:
        results = client.search_repositories(payload.query.strip(), per_page=payload.limit, sort=payload.sort)
    except GitHubError as exc:
        _METRICS["github_errors"] += 1
        raise HTTPException(status_code=502, detail="upstream GitHub service unavailable") from exc
    try:
        return SearchHistoryStore(os.environ.get("SNB_SEARCH_HISTORY_DB", "data/search_history.db")).record(
            payload.name, payload.query, results
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/search-history", tags=["private"])
def list_search_history(
    name: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=20, ge=1, le=20),
    x_api_key: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    require_api_key(x_api_key)
    try:
        return SearchHistoryStore(os.environ.get("SNB_SEARCH_HISTORY_DB", "data/search_history.db")).list(name, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/search-history/{name}/compare", tags=["private"])
def compare_search_history(
    name: str,
    snapshot_id: str | None = Query(default=None, max_length=80),
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        result = SearchHistoryStore(os.environ.get("SNB_SEARCH_HISTORY_DB", "data/search_history.db")).compare(
            name, snapshot_id=snapshot_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="search snapshot not found") from exc
    if result is None:
        raise HTTPException(status_code=404, detail="search history not found")
    return result


class WatchlistCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=2, max_length=100)
    min_score: float = Field(default=0, ge=0, le=1000)
    domains: list[str] = Field(default_factory=list, max_length=20)
    interval_minutes: int = Field(default=1440, ge=15, le=43200)


class WatchlistToggle(BaseModel):
    enabled: bool


@app.get("/api/watchlists", tags=["private"])
def list_watchlists(x_api_key: str | None = Header(default=None)) -> list[dict[str, Any]]:
    require_api_key(x_api_key)
    return WatchlistStore(os.environ.get("SNB_WATCHLIST_DB", "data/watchlists.db")).list()


@app.post("/api/watchlists", status_code=201, tags=["private"])
def create_watchlist(payload: WatchlistCreate, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        return WatchlistStore(os.environ.get("SNB_WATCHLIST_DB", "data/watchlists.db")).create(
            payload.name, payload.query, min_score=payload.min_score,
            domains=payload.domains, interval_minutes=payload.interval_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/watchlists/{watchlist_id}/enabled", tags=["private"])
def toggle_watchlist(watchlist_id: str, payload: WatchlistToggle, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        return WatchlistStore(os.environ.get("SNB_WATCHLIST_DB", "data/watchlists.db")).set_enabled(watchlist_id, payload.enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="watchlist not found") from exc


@app.get("/api/watchlists/due", tags=["private"])
def due_watchlists(x_api_key: str | None = Header(default=None)) -> list[dict[str, Any]]:
    require_api_key(x_api_key)
    return WatchlistStore(os.environ.get("SNB_WATCHLIST_DB", "data/watchlists.db")).due()


@app.get("/api/alerts", tags=["private"])
def alerts(
    run: int | None = Query(default=None, ge=1),
    min_move: float = Query(default=2.0, ge=0, le=1000),
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    require_api_key(x_api_key)
    return changes_since_previous_run(
        History(load_settings().history_db),
        run,
        min_move=min_move,
    )


@app.get("/api/alerts/events", tags=["private"])
def alert_events(
    status: str | None = Query(default=None, pattern="^(pending|acknowledged)$"),
    limit: int = Query(default=100, ge=1, le=500),
    x_api_key: str | None = Header(default=None),
) -> list[dict[str, Any]]:
    require_api_key(x_api_key)
    try:
        return AlertStore(os.environ.get("SNB_ALERTS_DB", "data/alerts.db")).list(
            status=status, limit=limit
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/alerts/events/{event_id}/acknowledge", tags=["private"])
def acknowledge_alert_event(
    event_id: str,
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        return AlertStore(os.environ.get("SNB_ALERTS_DB", "data/alerts.db")).acknowledge(event_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="alert event not found") from exc


@app.get("/api/workspaces", tags=["private"])
def list_workspaces(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    return {"workspaces": get_workspaces().list()}


@app.post("/api/workspaces", tags=["private"], status_code=201)
def create_workspace(payload: WorkspaceCreate, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    return get_workspaces().create(payload.title)


@app.get("/api/workspaces/{workspace_id}", tags=["private"])
def get_workspace(workspace_id: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        return get_workspaces().get(workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc


@app.patch("/api/workspaces/{workspace_id}", tags=["private"])
def update_workspace(workspace_id: str, payload: WorkspaceUpdate, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        return get_workspaces().update(workspace_id, status=payload.status, tags=payload.tags)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc


@app.post("/api/workspaces/{workspace_id}/items", tags=["private"])
def add_workspace_item(workspace_id: str, payload: WorkspaceItem, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        if payload.source_url and not _public_github_url(payload.source_url):
            raise HTTPException(status_code=422, detail="source_url must be a public GitHub URL")
        return get_workspaces().add_item(workspace_id, payload.kind, payload.value, payload.label, payload.source_url)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/workspaces/{workspace_id}/explain", tags=["private"])
def explain_workspace(workspace_id: str, payload: WorkspaceExplain, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    """Generate an optional deterministic/AI explanation for a public engineer in a private workspace."""
    require_api_key(x_api_key)
    try:
        get_workspaces().get(workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc

    client = GitHubClient(load_settings().github_token)
    try:
        profile = client.get_user(payload.login)
        if not profile:
            raise HTTPException(status_code=404, detail="engineer not found")
        repos = client.list_user_repos(payload.login, limit=30)
    except GitHubError as exc:
        _METRICS["github_errors"] += 1
        raise HTTPException(status_code=502, detail="upstream unavailable") from exc

    recommendation = score_candidate(payload.login, repos, Profile.load())
    if recommendation is None:
        raise HTTPException(status_code=422, detail="no explainable security evidence")

    try:
        provider = build_provider(
            os.environ.get("AI_PROVIDER", "offline"),
            anthropic_key=os.environ.get("ANTHROPIC_API_KEY"),
            openai_key=os.environ.get("OPENAI_API_KEY"),
            anthropic_model=os.environ.get("ANTHROPIC_MODEL"),
            openai_model=os.environ.get("OPENAI_MODEL"),
        )
        explanation = provider.explain(recommendation)
    except IntelligenceError as exc:
        raise HTTPException(status_code=503, detail="intelligence provider unavailable") from exc

    source = "deterministic" if provider.name == "offline" else "ai"
    note = f"Explanation ({provider.name}): {explanation}"
    try:
        stored = get_workspaces().add_note(workspace_id, note, _public_github_url(profile.get("html_url")))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc

    AuditLog(os.environ.get("SNB_AUDIT_DB", "data/audit.db")).record(
        "workspace.explanation", subject=workspace_id, outcome="success",
        detail=f"provider={provider.name}; source={source}; login={payload.login}",
    )
    return {"workspace_id": workspace_id, "login": payload.login, "explanation": explanation,
            "source": source, "provider": provider.name, "note_id": stored.get("id")}


@app.post("/api/workspaces/{workspace_id}/notes", tags=["private"])
def add_workspace_note(workspace_id: str, payload: WorkspaceNote, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        if payload.source_url and not _public_github_url(payload.source_url):
            raise HTTPException(status_code=422, detail="source_url must be a public GitHub URL")
        return get_workspaces().add_note(workspace_id, payload.body, payload.source_url)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/workspaces/{workspace_id}/export", tags=["private"])
def export_workspace(workspace_id: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    try:
        data = get_workspaces().get(workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc
    return {"schema_version": 1, "exported_at": datetime.now(timezone.utc).isoformat(), "workspace": data}


@app.delete("/api/workspaces/{workspace_id}", status_code=204, tags=["private"])
def delete_workspace(workspace_id: str, x_api_key: str | None = Header(default=None)) -> Response:
    require_api_key(x_api_key)
    try:
        get_workspaces().delete(workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc
    return Response(status_code=204)


@app.get("/api/public/engineers/{login}/relationships", tags=["public"])
def public_engineer_relationships(request: Request, response: Response, login: str) -> dict[str, Any]:
    _check_public_rate(request, "relationships", response)
    if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", login):
        raise HTTPException(status_code=422, detail="invalid GitHub login")
    data = get_history().get_run(get_history().latest_run_id()) if get_history().latest_run_id() else None
    graph_data = {} if not data else data.get("graph", {})
    edges = [e for e in graph_data.get("edges", []) if e.get("a") == login or e.get("b") == login]
    edges.sort(key=lambda e: (-float(e.get("weight", 0)), str(e.get("a", "")), str(e.get("b", ""))))
    return {"login": login, "source": "public GitHub-derived graph", "relationships": edges[:100]}


@app.get("/api/graph", response_model=GraphResponse, tags=["public"])
def graph(
    request: Request,
    response: Response,
    community: int | None = Query(default=None, ge=0, le=10000),
    min_centrality: float = Query(default=0, ge=0, le=1),
    edge_type: str | None = Query(default=None, pattern="^(contributor|organization|domain)$"),
    node_type: str = Query(default="engineer", pattern="^engineer$"),
    max_nodes: int = Query(default=250, ge=1, le=500),
) -> GraphResponse:
    """Return a deterministic filtered graph snapshot from the latest public run."""
    _check_public_rate(request, "graph", response)
    _METRICS["graphs"] += 1
    h = get_history()
    run_id = h.latest_run_id()
    filters = {"community": community, "min_centrality": min_centrality, "edge_type": edge_type, "node_type": node_type, "max_nodes": max_nodes}
    generated_at = datetime.now(timezone.utc).isoformat()
    if run_id is None:
        return GraphResponse(nodes=[], edges=[], communities=[], generated_at=generated_at, snapshot_created_at=None, run_id=None, source="snb-analysis", filters=filters)
    data = h.get_run(run_id)
    if not data:
        return GraphResponse(nodes=[], edges=[], communities=[], generated_at=generated_at, snapshot_created_at=None, run_id=run_id, source="snb-analysis", filters=filters)
    raw = data.get("graph", {"nodes": [], "edges": [], "communities": []})
    snapshot_created_at = (data.get("run") or {}).get("created_at")
    nodes = [n for n in raw.get("nodes", []) if float(n.get("centrality", 0)) >= min_centrality and (community is None or n.get("community") == community)]
    nodes.sort(key=lambda n: (-float(n.get("centrality", 0)), -float(n.get("score", 0)), str(n.get("login", "")).lower()))
    nodes = nodes[:max_nodes]
    allowed = {n.get("login") for n in nodes}
    edges = []
    for edge in raw.get("edges", []):
        if edge.get("a") not in allowed or edge.get("b") not in allowed:
            continue
        reasons = [str(x) for x in (edge.get("reasons") or [])]
        if edge_type == "contributor" and not any(x.startswith("both contribute") for x in reasons):
            continue
        if edge_type == "organization" and not any(x.startswith("both in org") for x in reasons):
            continue
        if edge_type == "domain" and not any("shared domains" in x for x in reasons):
            continue
        edges.append(edge)
    communities = [c for c in raw.get("communities", []) if any(m in allowed for m in c.get("members", []))]
    return GraphResponse(nodes=nodes, edges=edges, communities=communities, generated_at=generated_at, snapshot_created_at=snapshot_created_at, run_id=run_id, source="snb-analysis", filters=filters)