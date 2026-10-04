"""Execute scheduled watchlists through the durable local worker.

A watchlist run is deliberately bounded: one GitHub repository search produces
seed repositories, candidates are scored from that public evidence, and the
result is persisted to the normal History store. No outreach or notification
is performed.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from .config import Profile
from .discovery import build_query
from .github_api import GitHubClient, GitHubError, RateLimitError
from .graph import build_graph
from .history import History
from .models import Candidate
from .orgs import analyze_orgs
from .scoring import score_candidate


def _now() -> datetime:
    return datetime.now(timezone.utc)


def run_watchlist(
    payload: dict[str, Any],
    *,
    client: GitHubClient | None = None,
    history: History | None = None,
) -> str:
    """Run one bounded watchlist discovery and persist its results."""
    query = str(payload.get("query", "")).strip()
    if not 2 <= len(query) <= 100:
        raise ValueError("invalid watchlist query")

    profile = Profile.load(payload.get("profile") or None)
    client = client or GitHubClient(os.environ.get("GITHUB_TOKEN") or None)
    history = history or History(payload.get("history_db") or "data/history.db")

    search_query = build_query(query, profile)
    try:
        repos = client.search_repositories(
            search_query,
            per_page=min(profile.settings.results_per_query, 30),
        )
    except (GitHubError, RateLimitError) as exc:
        raise RuntimeError(f"watchlist discovery failed: {type(exc).__name__}") from exc

    excluded = {u.lower() for u in profile.settings.exclude_users}
    if profile.github_username:
        excluded.add(profile.github_username.lower())

    candidates: dict[str, Candidate] = {}
    for repo in repos:
        owner = repo.get("owner") or {}
        login = str(owner.get("login") or "").strip()
        if not login or login.lower() in excluded:
            continue
        if profile.settings.users_only and owner.get("type") != "User":
            continue
        candidate = candidates.setdefault(
            login,
            Candidate(login=login, html_url=owner.get("html_url", f"https://github.com/{login}")),
        )
        candidate.seed_repos.append(repo)
        candidate.queries.add(query)

    max_candidates = min(profile.settings.max_candidates, 30)
    ranked = sorted(candidates.values(), key=lambda item: item.seed_weight, reverse=True)[:max_candidates]
    min_score = float(payload.get("min_score", 0))

    recommendations = []
    for candidate in ranked:
        recommendation = score_candidate(
            candidate.login,
            list(candidate.seed_repos),
            profile,
        )
        if recommendation is None or recommendation.score < min_score:
            continue
        recommendation.via = f"watchlist:{payload.get('watchlist_id', 'manual')}"
        recommendations.append(recommendation)

    recommendations.sort(key=lambda item: item.score, reverse=True)
    graph = build_graph(recommendations, {})
    org_summary = analyze_orgs(recommendations)
    run_id = history.save_run(
        recommendations,
        profile.name,
        "watchlist",
        graph.to_dict(),
        org_summary,
    )
    return f"watchlist run {run_id}: {len(recommendations)} recommendations"


def build_watchlist_payload(item: dict[str, Any], *, history_db: str) -> dict[str, Any]:
    """Build the stable, bounded payload stored in the durable job queue."""
    return {
        "watchlist_id": str(item["id"]),
        "query": str(item["query"])[:100],
        "min_score": float(item["min_score"]),
        "domains": [str(x)[:80] for x in item.get("domains", [])][:20],
        "history_db": history_db,
    }
