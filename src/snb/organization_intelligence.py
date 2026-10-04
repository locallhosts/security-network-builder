"""Deterministic organization intelligence from public recommendations."""
from __future__ import annotations

from collections import Counter
from typing import Any

from .models import Recommendation


def analyze_organization_intelligence(recs: list[Recommendation], *, max_orgs: int = 50) -> list[dict[str, Any]]:
    """Aggregate organization concentration without making additional API calls.

    Metrics are derived only from already collected public recommendation data.
    """
    if not 1 <= max_orgs <= 100:
        raise ValueError("max_orgs must be between 1 and 100")

    groups: dict[str, list[Recommendation]] = {}
    for rec in recs:
        for org in dict.fromkeys(x.strip() for x in rec.orgs if x.strip()):
            groups.setdefault(org, []).append(rec)

    total_score = sum(max(0.0, r.score) for r in recs)
    output: list[dict[str, Any]] = []
    for org, members in groups.items():
        domains = Counter(d for r in members for d in r.matched_domains)
        member_scores = sorted((float(r.score) for r in members), reverse=True)
        concentration = (sum(member_scores) / total_score * 100.0) if total_score else 0.0
        output.append(
            {
                "login": org,
                "url": f"https://github.com/{org}",
                "member_count": len(members),
                "members": sorted({r.login for r in members}),
                "total_score": round(sum(member_scores), 1),
                "avg_score": round(sum(member_scores) / len(member_scores), 1),
                "top_member_score": round(member_scores[0], 1),
                "score_share_percent": round(concentration, 1),
                "domain_diversity": len(domains),
                "top_domains": [d for d, _ in domains.most_common(5)],
            }
        )

    output.sort(
        key=lambda item: (
            item["member_count"],
            item["score_share_percent"],
            item["total_score"],
            item["login"].lower(),
        ),
        reverse=True,
    )
    return output[:max_orgs]
