"""Security Network Builder: discover and rank security engineers on GitHub.

Read-only: this tool never follows, stars, or messages anyone. It produces a
report; any outreach is a manual decision.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys

from config import Profile, load_env
from discovery import discover
from github_api import GitHubClient, GitHubError, RateLimitError
from report import render_console, write_reports
from scoring import score_candidate


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Security engineer discovery and ranking")
    p.add_argument("--profile", default="profiles/security_profile.yaml", help="path to profile YAML")
    p.add_argument("--top", type=int, default=15, help="number of engineers in the report")
    p.add_argument("--min-score", type=float, default=0.0, help="drop engineers below this score")
    p.add_argument("--queries-per-domain", type=int, default=None, help="limit searches per domain (saves rate limit)")
    p.add_argument("--max-candidates", type=int, default=None, help="override settings.max_candidates")
    p.add_argument("--output-dir", default="reports")
    p.add_argument("--format", choices=["md", "json", "both"], default="both")
    p.add_argument("--no-report", action="store_true", help="print only, write no files")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    load_env()
    token = os.environ.get("GITHUB_TOKEN") or None
    if not token:
        print("Warning: GITHUB_TOKEN not set. Anonymous API limits are low (10 searches/min, 60 calls/hour).\n")

    profile = Profile.load(args.profile)
    client = GitHubClient(token)
    print("Building security network...\n")

    recs = []
    try:
        candidates = discover(client, profile, args.queries_per_domain, progress=print)
    except RateLimitError as exc:
        print(f"Stopped during discovery: {exc}", file=sys.stderr)
        return 2
    except GitHubError as exc:
        print(f"GitHub error: {exc}", file=sys.stderr)
        return 1

    max_c = args.max_candidates or profile.settings.max_candidates
    ranked = sorted(candidates.values(), key=lambda c: c.seed_weight, reverse=True)[:max_c]
    print(f"Found {len(candidates)} engineers; analysing top {len(ranked)}...\n")

    try:
        for cand in ranked:
            repos = client.list_user_repos(cand.login, profile.settings.max_repos_per_user)
            # Seed repos come from search and carry the same fields, so merge them in.
            seen = {r.get("full_name") for r in repos}
            repos += [r for r in cand.seed_repos if r.get("full_name") not in seen]
            rec = score_candidate(cand.login, repos, profile)
            if rec and rec.score >= args.min_score:
                recs.append(rec)
    except RateLimitError as exc:
        print(f"Rate limit hit; continuing with {len(recs)} engineers analysed so far ({exc})\n", file=sys.stderr)
    except GitHubError as exc:
        print(f"GitHub error during analysis: {exc}", file=sys.stderr)

    recs.sort(key=lambda r: r.score, reverse=True)
    recs = recs[: args.top]

    try:  # enrich only the final list to save API calls
        for rec in recs:
            u = client.get_user(rec.login)
            rec.profile = {k: u.get(k) for k in ("name", "bio", "company", "location", "followers", "blog")}
    except GitHubError:
        pass  # enrichment is optional

    print(render_console(recs))
    if recs and not args.no_report:
        for path in write_reports(recs, args.output_dir, profile.name, args.format):
            print(f"Report written: {path}")
    return 0


def main() -> None:
    sys.exit(run(parse_args()))


if __name__ == "__main__":
    main()
