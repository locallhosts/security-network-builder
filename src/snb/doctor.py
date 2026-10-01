"""`snb doctor`: verify everything a run depends on, before it fails halfway through."""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import __version__
from .config import Profile, load_env
from .github_api import GitHubClient, GitHubError

SEARCH_INTERVAL = {True: 2.1, False: 6.5}   # seconds between searches, with / without token


@dataclass
class Check:
    status: str      # ok | warn | fail | info
    name: str
    detail: str = ""


def _writable(directory: str) -> str | None:
    try:
        Path(directory).mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=directory):
            pass
        return None
    except OSError as exc:
        return str(exc)


def run_checks(profile_path: str | None, client: GitHubClient | None, offline: bool, history_db: str, output_dir: str, env=os.environ) -> list[Check]:
    checks: list[Check] = []
    add = lambda status, name, detail="": checks.append(Check(status, name, detail))
    token = env.get("GITHUB_TOKEN") or None

    if sys.version_info < (3, 10):
        add("fail", "Python", f"{sys.version.split()[0]}; 3.10+ required")
    else:
        add("ok", "Python", f"{sys.version.split()[0]}, snb {__version__}")

    # Profile
    profile = None
    try:
        profile = Profile.load(profile_path)
        n_queries = sum(len(d.search_queries) for d in profile.domains)
        add("ok", "Profile", f"{profile.name}: {len(profile.domains)} domains, {n_queries} search queries")
        if not profile.github_username:
            add("warn", "Profile github_username", "empty; you may show up in your own results")
        for d in profile.domains:
            if not d.search_queries:
                add("warn", f"Domain '{d.key}'", "no search_queries: it scores repos but never drives discovery")
    except (OSError, ValueError, AttributeError, TypeError) as exc:
        add("fail", "Profile", str(exc))

    # Local paths
    for label, path in (("History directory", str(Path(history_db).parent)), ("Report directory", output_dir)):
        err = _writable(path)
        add("fail" if err else "ok", label, err or f"{path} is writable")

    # Optional LLM
    add("ok" if env.get("ANTHROPIC_API_KEY") else "info", "LLM (--ai)", "ANTHROPIC_API_KEY set" if env.get("ANTHROPIC_API_KEY") else "not set; --ai will use offline explanations")

    if offline:
        add("info", "Network checks", "skipped (--offline)")
        return checks

    # GitHub token and quota
    add("ok" if token else "warn", "GITHUB_TOKEN", "set" if token else "not set: anonymous mode (10 searches/min, 60 calls/hour, no GraphQL)")
    client = client or GitHubClient(token)
    try:
        res = client.rate_limit()
    except GitHubError as exc:
        add("fail", "GitHub API", f"{exc}" + ("; token rejected?" if "401" in str(exc) else ""))
        return checks
    core, search, gql = (res.get(k, {}) for k in ("core", "search", "graphql"))
    add("ok", "GitHub API", f"core {core.get('remaining')}/{core.get('limit')}, search {search.get('remaining')}/{search.get('limit')}"
        + (f", graphql {gql.get('remaining')}/{gql.get('limit')}" if gql else ""))

    scopes = client.last_headers.get("X-OAuth-Scopes", "").strip()
    if token and scopes:
        add("warn", "Token scopes", f"classic token has scopes [{scopes}]; this tool reads public data only, so no scopes are needed")
    elif token:
        add("ok", "Token scopes", "no broad scopes detected")

    if token:
        try:
            client.graphql("query { viewer { login } }")
            add("ok", "GraphQL", "works; batched mode will be used")
        except GitHubError as exc:
            add("warn", "GraphQL", f"unavailable ({exc}); REST fallback will be used")

    if profile:
        n = sum(len(d.search_queries) for d in profile.domains)
        secs = int(n * SEARCH_INTERVAL[bool(token)])
        left = search.get("remaining")
        if left is not None and left < n:
            add("warn", "Search budget", f"{n} queries planned but only {left} left this minute; the run will pause to wait")
        else:
            add("ok", "Search budget", f"{n} queries planned, about {secs}s of discovery")
    return checks


def render(checks: list[Check]) -> str:
    tag = {"ok": " OK ", "warn": "WARN", "fail": "FAIL", "info": "INFO"}
    return "\n".join(f"[{tag[c.status]}] {c.name}" + (f": {c.detail}" if c.detail else "") for c in checks)


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(prog="snb doctor", description="Check your setup before a run")
    p.add_argument("--profile", default=None)
    p.add_argument("--history-db", default="data/history.db")
    p.add_argument("--output-dir", default="reports")
    p.add_argument("--offline", action="store_true", help="skip GitHub network checks")
    args = p.parse_args(argv)
    load_env()
    checks = run_checks(args.profile, None, args.offline, args.history_db, args.output_dir)
    print(render(checks))
    failed = sum(c.status == "fail" for c in checks)
    warned = sum(c.status == "warn" for c in checks)
    print(f"\n{'Not ready' if failed else 'Ready'}: {failed} failed, {warned} warning(s).")
    return 1 if failed else 0
