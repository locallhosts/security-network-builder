"""FastAPI application for the public Security Network Builder API."""

from __future__ import annotations

import os
import re
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
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ..audit import AuditLog
from ..config import Profile
from ..github_api import GitHubClient, GitHubError
from ..history import History
from ..jobs import JobQueue
from ..readiness import readiness
from ..workspace import WorkspaceStore
from ..scoring import score_candidate

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


class GraphResponse(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]
    communities: list[Any]
    generated_at: str | None = None
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


_SEARCH_WINDOW = 60.0
_SEARCH_LIMIT = 30
_search_hits: dict[str, deque[float]] = defaultdict(deque)


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
    correlation_id = request.headers.get("X-Request-ID") or secrets.token_hex(12)
    request.state.correlation_id = correlation_id
    response = await call_next(request)
    response.headers.setdefault("X-Request-ID", correlation_id)
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


@app.get("/api/readiness", tags=["public"])
def readiness_endpoint() -> dict[str, Any]:
    return readiness()


@app.get("/api/health", response_model=HealthResponse, tags=["public"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service="security-network-builder")


@app.get("/api/search", response_model=SearchResponse, tags=["public"])
def search(
    request: Request,
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
    response: Response = None,
) -> SearchResponse:
    """Search public GitHub repositories. No private API key is exposed to browsers."""
    _check_search_rate(request)
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
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
    return SearchResponse(query=q, page=page, limit=limit, results=results)


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
        raise HTTPException(status_code=502, detail=str(exc)) from exc

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
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(10, ge=1, le=30),
    page: int = Query(1, ge=1, le=34),
    sort: str = Query("followers", pattern="^(followers|repositories|joined)$"),
) -> UserSearchResponse:
    """Search public GitHub users without exposing credentials to the browser."""
    _check_search_rate(request)
    client = GitHubClient(load_settings().github_token)
    try:
        items = client.search_users(q.strip(), per_page=limit, page=page, sort=sort)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

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
    return UserSearchResponse(query=q, page=page, limit=limit, results=results)


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
        repositories = client.list_user_repos(login, limit=30)
        organizations = client.list_user_orgs(login)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

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
    )


@app.get("/api/usage", tags=["public"])
def usage(request: Request, response: Response) -> dict[str, Any]:
    _check_search_rate(request)
    client = GitHubClient(load_settings().github_token)
    try:
        resources = client.rate_limit()
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    response.headers["X-Data-Source"] = "github"
    return {"source": "github", "core": resources.get("core") or {}, "search": resources.get("search") or {}, "generated_at": datetime.now(timezone.utc).isoformat()}


@app.get("/api/usage", tags=["public"])
def usage(request: Request, response: Response) -> dict[str, Any]:
    _check_search_rate(request)
    client = GitHubClient(load_settings().github_token)
    try:
        resources = client.rate_limit()
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    response.headers["X-Data-Source"] = "github"
    return {"source": "github", "core": resources.get("core") or {}, "search": resources.get("search") or {}, "generated_at": datetime.now(timezone.utc).isoformat()}


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


@app.delete("/api/workspaces/{workspace_id}", status_code=204, tags=["private"])
def delete_workspace(workspace_id: str, x_api_key: str | None = Header(default=None)) -> Response:
    require_api_key(x_api_key)
    try:
        get_workspaces().delete(workspace_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="workspace not found") from exc
    return Response(status_code=204)


@app.get("/api/graph", response_model=GraphResponse, tags=["public"])
def graph(
    community: int | None = Query(default=None, ge=0, le=10000),
    min_centrality: float = Query(default=0, ge=0, le=1),
    edge_type: str | None = Query(default=None, pattern="^(contributor|organization|domain)$"),
    node_type: str = Query(default="engineer", pattern="^engineer$"),
    max_nodes: int = Query(default=250, ge=1, le=500),
) -> GraphResponse:
    """Return a deterministic filtered graph snapshot from the latest public run."""
    h = get_history()
    run_id = h.latest_run_id()
    filters = {"community": community, "min_centrality": min_centrality, "edge_type": edge_type, "node_type": node_type, "max_nodes": max_nodes}
    generated_at = datetime.now(timezone.utc).isoformat()
    if run_id is None:
        return GraphResponse(nodes=[], edges=[], communities=[], generated_at=generated_at, filters=filters)
    data = h.get_run(run_id)
    if not data:
        return GraphResponse(nodes=[], edges=[], communities=[], generated_at=generated_at, filters=filters)
    raw = data.get("graph", {"nodes": [], "edges": [], "communities": []})
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
    return GraphResponse(nodes=nodes, edges=edges, communities=communities, generated_at=generated_at, filters=filters)
