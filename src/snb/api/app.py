"""FastAPI application for the public Security Network Builder API."""

from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query

from ..history import History
from ..github_api import GitHubClient, GitHubError

app = FastAPI(title="Security Network Builder API", version="1.0.0")
DB_PATH = os.environ.get("SNB_HISTORY_DB", "data/history.db")


def get_history() -> History:
    return History(DB_PATH)


def require_api_key(value: str | None) -> None:
    configured = os.environ.get("API_KEY")
    if configured and value != configured:
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "security-network-builder"}


@app.get("/api/search")
def search(q: str = Query(..., min_length=2, max_length=100), limit: int = Query(10, ge=1, le=30), x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    client = GitHubClient(os.environ.get("GITHUB_TOKEN") or None)
    try:
        items = client.search_repositories(q, per_page=limit)
    except GitHubError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    results = []
    for item in items:
        owner = item.get("owner") or {}
        results.append({"repository": item.get("full_name"), "description": item.get("description"), "stars": item.get("stargazers_count", 0), "language": item.get("language"), "owner": owner.get("login"), "url": item.get("html_url")})
    return {"query": q, "results": results}

@app.get("/api/runs")
def runs(limit: int = Query(20, ge=1, le=100), x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    return {"runs": get_history().runs(limit)}


@app.get("/api/runs/latest")
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


@app.get("/api/runs/{run_id}")
def get_run(run_id: int, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    data = get_history().get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="run not found")
    return data


@app.get("/api/engineers/{login}")
def engineer(login: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    return {"login": login, "history": get_history().engineer_history(login)}


@app.get("/api/graph")
def graph(x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    require_api_key(x_api_key)
    h = get_history()
    run_id = h.latest_run_id()
    if run_id is None:
        raise HTTPException(status_code=404, detail="no runs recorded")
    data = h.get_run(run_id)
    if not data:
        raise HTTPException(status_code=404, detail="run not found")
    return data.get("graph", {"nodes": [], "edges": [], "communities": []})
