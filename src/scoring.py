"""Explainable scoring engine.

Score = sum of domain points + activity bonus + traction bonus + language bonus.
Every point is recorded in `breakdown` and backed by a line in `evidence`.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from config import Profile
from models import Recommendation

EXTRA_REPO_POINTS = 1.0   # per additional matching repo in the same domain
EXTRA_REPO_CAP = 3        # ...up to this many extra repos
ACTIVE_90D = 3.0
ACTIVE_365D = 1.0
LANGUAGE_BONUS = 1.0


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def score_candidate(
    login: str,
    repos: list[dict[str, Any]],
    profile: Profile,
    now: datetime | None = None,
) -> Recommendation | None:
    """Score one engineer from their public repos. Returns None if nothing matches."""
    now = now or datetime.now(timezone.utc)
    s = profile.settings

    hits: dict[str, list[tuple[dict[str, Any], set[str]]]] = {}
    for repo in repos:
        if repo.get("archived"):
            continue
        if repo.get("fork") and not s.include_forks:
            continue
        for key, kws in profile.match_repo(repo).items():
            hits.setdefault(key, []).append((repo, kws))
    if not hits:
        return None

    breakdown: dict[str, float] = {}
    evidence: list[str] = []
    matched: dict[str, dict[str, Any]] = {}

    for domain in profile.domains:
        entries = hits.get(domain.key)
        if not entries:
            continue
        extra = min(len(entries) - 1, EXTRA_REPO_CAP)
        breakdown[domain.label] = domain.weight + extra * EXTRA_REPO_POINTS
        best_repo, best_kws = max(entries, key=lambda e: e[0].get("stargazers_count", 0))
        name = best_repo.get("full_name") or f"{login}/{best_repo.get('name')}"
        evidence.append(f"{domain.label}: {name} ({', '.join(sorted(best_kws))})")
        for repo, _ in entries:
            matched[repo.get("full_name") or repo.get("name", "")] = repo

    # Activity: how recently a matching repo was pushed to
    pushes = [t for t in (_parse_ts(r.get("pushed_at")) for r in matched.values()) if t]
    if pushes:
        age = (now - max(pushes)).days
        if age <= 90:
            breakdown["Recent activity"] = ACTIVE_90D
            evidence.append(f"Active: matching repo pushed {age} day(s) ago")
        elif age <= 365:
            breakdown["Recent activity"] = ACTIVE_365D
            evidence.append(f"Maintained: last matching push {age} days ago")

    # Traction: log-scaled stars on matching repos (capped so popularity can't dominate)
    stars = sum(r.get("stargazers_count", 0) for r in matched.values())
    traction = min(3, int(math.log10(stars + 1)))
    if traction:
        breakdown["Community traction"] = float(traction)
        evidence.append(f"{stars} stars across {len(matched)} matching repo(s)")

    # Preferred languages
    preferred = {l.lower() for l in s.preferred_languages}
    langs = {r.get("language") for r in matched.values() if (r.get("language") or "").lower() in preferred}
    if langs:
        breakdown["Preferred language"] = LANGUAGE_BONUS
        evidence.append(f"Builds security tooling in {', '.join(sorted(langs))}")

    top_repos = sorted(matched.values(), key=lambda r: r.get("stargazers_count", 0), reverse=True)[:5]
    return Recommendation(
        login=login,
        url=f"https://github.com/{login}",
        score=round(sum(breakdown.values()), 1),
        matched_domains=[d.label for d in profile.domains if d.label in breakdown],
        breakdown=breakdown,
        evidence=evidence,
        matched_repos=[
            {
                "name": r.get("full_name") or r.get("name"),
                "url": r.get("html_url"),
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language"),
                "description": r.get("description"),
            }
            for r in top_repos
        ],
    )
