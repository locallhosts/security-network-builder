"""Shared data models."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Candidate:
    """An engineer found during discovery, before deep analysis."""

    login: str
    html_url: str
    seed_repos: list[dict[str, Any]] = field(default_factory=list)
    queries: set[str] = field(default_factory=set)

    @property
    def seed_weight(self) -> int:
        """Rough pre-ranking used to decide who gets analysed first."""
        return len(self.queries) * 10 + sum(r.get("stargazers_count", 0) for r in self.seed_repos)


@dataclass
class Recommendation:
    """A scored, explainable engineer recommendation."""

    login: str
    url: str
    score: float
    matched_domains: list[str]
    breakdown: dict[str, float]
    evidence: list[str]
    matched_repos: list[dict[str, Any]]
    profile: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
