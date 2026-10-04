"""Compare security profiles against the same public GitHub candidates."""
from __future__ import annotations

from typing import Any

from .config import Profile
from .github_api import GitHubClient, GitHubError
from .scoring import score_candidate


def compare_profiles(
    client: GitHubClient,
    profiles: dict[str, Profile],
    logins: list[str],
    *,
    max_repos: int = 100,
) -> dict[str, Any]:
    """Score the same bounded candidate set with multiple profiles.

    Repository data is fetched once per candidate and reused across profiles.
    """
    if not profiles:
        raise ValueError("at least one profile is required")
    if not 1 <= len(profiles) <= 10:
        raise ValueError("profiles must contain between 1 and 10 entries")
    candidates = list(dict.fromkeys(x.strip() for x in logins if x.strip().lower()))
    if not 1 <= len(candidates) <= 30:
        raise ValueError("logins must contain between 1 and 30 users")
    if not 1 <= max_repos <= 100:
        raise ValueError("max_repos must be between 1 and 100")

    output: dict[str, Any] = {"profiles": list(profiles), "candidates": []}
    for login in candidates:
        try:
            repos = client.list_user_repos(login, max_repos)
        except GitHubError:
            repos = []
        scores: dict[str, Any] = {}
        for name, profile in profiles.items():
            rec = score_candidate(login, list(repos), profile)
            scores[name] = rec.to_dict() if rec else None
        output["candidates"].append({"login": login, "profiles": scores})
    return output
