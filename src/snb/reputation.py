"""Reputation signals beyond popularity.

Followers alone are a weak, gameable signal, so they are only one of four
capped components. Contribution volume, code review, and tenure are
harder to fake and say more about sustained engineering work.

Max total: 6 points (REPUTATION_CAP).
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

REPUTATION_CAP = 6.0


def _years_since(ts: str | None, now: datetime) -> float:
    if not ts:
        return 0.0
    try:
        created = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return 0.0
    return max(0.0, (now - created).days / 365.25)


def compute_reputation(stats: dict[str, Any], now: datetime | None = None) -> tuple[float, str]:
    """Return (points, evidence_line). Missing stats simply contribute nothing."""
    now = now or datetime.now(timezone.utc)
    points = 0.0
    notes: list[str] = []

    followers = int(stats.get("followers") or 0)
    f_pts = min(2, int(math.log10(followers + 1)))          # 9->1, 99->2 (capped)
    if f_pts:
        points += f_pts
        notes.append(f"{followers} followers")

    activity = sum(int(stats.get(k) or 0) for k in ("commits", "pull_requests", "reviews", "issues"))
    a_pts = 2 if activity >= 1000 else 1 if activity >= 200 else 0
    if a_pts:
        points += a_pts
        notes.append(f"{activity} contributions in the last year")

    reviews = int(stats.get("reviews") or 0)
    if reviews >= 25:
        points += 1
        notes.append(f"{reviews} code reviews")

    years = _years_since(stats.get("created_at"), now)
    if years >= 3:
        points += 1
        notes.append(f"{int(years)}-year-old account")

    points = min(points, REPUTATION_CAP)
    if not points:
        return 0.0, ""
    return points, f"Reputation: {', '.join(notes)}"
