"""Discovery engine: turns the security profile into GitHub searches."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Callable

from config import Profile
from github_api import GitHubClient, GitHubError, RateLimitError
from models import Candidate

log = logging.getLogger(__name__)


def build_query(query: str, profile: Profile, now: datetime | None = None) -> str:
    s = profile.settings
    now = now or datetime.now(timezone.utc)
    since = (now - timedelta(days=s.active_within_days)).strftime("%Y-%m-%d")
    parts = [query]
    if "topic:" not in query:
        parts.append("in:name,description,topics")
    parts.append(f"stars:>={s.min_stars}")
    parts.append(f"pushed:>{since}")
    parts.append("archived:false")
    if not s.include_forks:
        parts.append("fork:false")
    return " ".join(parts)


def discover(
    client: GitHubClient,
    profile: Profile,
    queries_per_domain: int | None = None,
    progress: Callable[[str], None] = lambda _msg: None,
) -> dict[str, Candidate]:
    """Run searches and group the repository owners into candidates."""
    s = profile.settings
    excluded = {u.lower() for u in s.exclude_users}
    if profile.github_username:
        excluded.add(profile.github_username.lower())

    candidates: dict[str, Candidate] = {}
    for domain in profile.domains:
        for raw in domain.search_queries[:queries_per_domain]:
            progress(f"Searching:\n{raw}\n")
            try:
                repos = client.search_repositories(build_query(raw, profile), per_page=s.results_per_query)
            except RateLimitError:
                raise
            except GitHubError as exc:
                log.warning("search failed for %r: %s", raw, exc)
                continue
            for repo in repos:
                owner = repo.get("owner") or {}
                login = owner.get("login")
                if not login or login.lower() in excluded:
                    continue
                if s.users_only and owner.get("type") != "User":
                    continue
                cand = candidates.setdefault(
                    login, Candidate(login=login, html_url=owner.get("html_url", f"https://github.com/{login}"))
                )
                cand.seed_repos.append(repo)
                cand.queries.add(raw)
    return candidates
