"""Organization analysis: which orgs concentrate the engineers you found.

Only public memberships are visible through the GitHub API.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

from .models import Recommendation


def analyze_orgs(recs: list[Recommendation]) -> list[dict[str, Any]]:
    """Group recommended engineers by organization, strongest first."""
    members: dict[str, list[Recommendation]] = {}
    for rec in recs:
        for org in rec.orgs:
            members.setdefault(org, []).append(rec)

    out = []
    for org, rs in members.items():
        domains = Counter(d for r in rs for d in r.matched_domains)
        out.append(
            {
                "login": org,
                "url": f"https://github.com/{org}",
                "members": sorted(r.login for r in rs),
                "total_score": round(sum(r.score for r in rs), 1),
                "avg_score": round(sum(r.score for r in rs) / len(rs), 1),
                "top_domains": [d for d, _ in domains.most_common(3)],
            }
        )
    # Orgs with several matching engineers are the interesting ones.
    out.sort(key=lambda o: (len(o["members"]), o["total_score"]), reverse=True)
    return out
