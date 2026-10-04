"""Deterministic health signals for public GitHub repositories.

The module is deliberately metadata-only: it does not clone repositories,
open issues, write to GitHub, or inspect private data.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .taxonomy import classify_repository


def _days_since(value: str | None, now: datetime) -> int | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, (now - dt.astimezone(timezone.utc)).days)


def assess_repository(repo: dict[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Return bounded, explainable health signals from public repository metadata.

    The score is a heuristic, not a security verdict. Missing metadata is treated
    as unknown rather than automatically unhealthy.
    """
    now = now or datetime.now(timezone.utc)
    age = _days_since(repo.get("pushed_at"), now)
    score = 100.0
    signals: list[dict[str, Any]] = []

    archived = bool(repo.get("archived"))
    disabled = bool(repo.get("disabled"))
    if archived:
        score -= 35
        signals.append({"id": "archived", "severity": "high", "detail": "Repository is archived."})
    if disabled:
        score -= 25
        signals.append({"id": "disabled", "severity": "high", "detail": "Repository is disabled."})

    if age is None:
        signals.append({"id": "activity_unknown", "severity": "info", "detail": "Push activity date is unavailable."})
    elif age > 730:
        score -= 25
        signals.append({"id": "stale", "severity": "high", "detail": f"No push activity for {age} days."})
    elif age > 90:
        score -= 10
        signals.append({"id": "aging", "severity": "medium", "detail": f"No push activity for {age} days."})
    else:
        signals.append({"id": "active", "severity": "positive", "detail": f"Updated within {age} days."})

    if repo.get("has_issues") is False:
        signals.append({"id": "issues_disabled", "severity": "info", "detail": "GitHub Issues are disabled."})
    if repo.get("license") is None:
        score -= 5
        signals.append({"id": "license_unknown", "severity": "low", "detail": "No public license metadata is reported."})
    else:
        signals.append({"id": "license_present", "severity": "positive", "detail": "Public license metadata is present."})

    if repo.get("security_and_analysis") is not None:
        signals.append({"id": "security_metadata", "severity": "positive", "detail": "GitHub security-analysis metadata is available."})

    score = round(max(0.0, min(100.0, score)), 1)
    if score >= 80:
        grade = "healthy"
    elif score >= 60:
        grade = "watch"
    elif score >= 40:
        grade = "aging"
    else:
        grade = "high-risk"

    return {
        "repository": str(repo.get("full_name") or repo.get("name") or ""),
        "url": str(repo.get("html_url") or ""),
        "score": score,
        "grade": grade,
        "activity_age_days": age,
        "signals": signals,
        "security_skills": classify_repository(repo),
        "limitations": [
            "Heuristic metadata assessment only; it is not a vulnerability scan.",
            "Missing GitHub metadata is treated as unknown.",
        ],
    }
