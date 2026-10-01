"""GraphQL fetching: one request returns repos, org memberships and contribution
stats for up to ~10 engineers, replacing 2-3 REST calls per engineer.

Results are normalised into the same dict shapes the REST API returns, so the
scoring engine does not care which transport was used.
"""
from __future__ import annotations

from typing import Any

from .github_api import GitHubClient

BATCH_SIZE = 10

_FRAGMENT = """
fragment F on User {
  login name bio company location websiteUrl createdAt
  followers { totalCount }
  organizations(first: 10) { nodes { login } }
  contributionsCollection {
    totalCommitContributions totalPullRequestContributions
    totalPullRequestReviewContributions totalIssueContributions
  }
  repositories(first: __N__, ownerAffiliations: OWNER, isFork: false,
               orderBy: {field: PUSHED_AT, direction: DESC}) {
    nodes {
      nameWithOwner name description url stargazerCount forkCount pushedAt
      isArchived isFork primaryLanguage { name }
      repositoryTopics(first: 20) { nodes { topic { name } } }
    }
  }
}
"""


def build_query(n_users: int, repo_limit: int = 50) -> str:
    decl = ", ".join(f"$l{i}: String!" for i in range(n_users))
    body = " ".join(f"u{i}: user(login: $l{i}) {{ ...F }}" for i in range(n_users))
    fragment = _FRAGMENT.replace("__N__", str(max(1, min(int(repo_limit), 100))))
    return f"query({decl}) {{ {body} }} {fragment}"


def normalize_user(node: dict[str, Any]) -> dict[str, Any]:
    repos = []
    for r in (node.get("repositories") or {}).get("nodes") or []:
        if not r:
            continue
        topics = [t["topic"]["name"] for t in (r.get("repositoryTopics") or {}).get("nodes") or [] if t]
        repos.append(
            {
                "name": r.get("name"),
                "full_name": r.get("nameWithOwner"),
                "html_url": r.get("url"),
                "description": r.get("description"),
                "topics": topics,
                "stargazers_count": r.get("stargazerCount", 0),
                "forks_count": r.get("forkCount", 0),
                "language": (r.get("primaryLanguage") or {}).get("name"),
                "pushed_at": r.get("pushedAt"),
                "fork": bool(r.get("isFork")),
                "archived": bool(r.get("isArchived")),
            }
        )
    c = node.get("contributionsCollection") or {}
    followers = (node.get("followers") or {}).get("totalCount", 0)
    stats = {
        "followers": followers,
        "commits": c.get("totalCommitContributions", 0),
        "pull_requests": c.get("totalPullRequestContributions", 0),
        "reviews": c.get("totalPullRequestReviewContributions", 0),
        "issues": c.get("totalIssueContributions", 0),
        "created_at": node.get("createdAt"),
        "orgs": [o["login"] for o in (node.get("organizations") or {}).get("nodes") or [] if o],
    }
    profile = {
        "name": node.get("name"),
        "bio": node.get("bio"),
        "company": node.get("company"),
        "location": node.get("location"),
        "followers": followers,
        "blog": node.get("websiteUrl"),
    }
    return {"login": node["login"], "repos": repos, "stats": stats, "profile": profile}


def fetch_users(client: GitHubClient, logins: list[str], repo_limit: int = 50) -> dict[str, dict[str, Any]]:
    """Fetch many engineers in as few requests as possible. Unknown users are omitted."""
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(logins), BATCH_SIZE):
        batch = logins[i : i + BATCH_SIZE]
        variables = {f"l{j}": login for j, login in enumerate(batch)}
        data, _errors = client.graphql(build_query(len(batch), repo_limit), variables)
        for node in data.values():
            if node:  # null for NOT_FOUND users
                out[node["login"]] = normalize_user(node)
    return out
