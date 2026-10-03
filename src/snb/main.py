"""Security Network Builder: discover and rank security engineers on GitHub.

Read-only: this tool never follows, stars, or messages anyone. It produces a
report and a local history; any outreach is your own manual decision.

Commands:
  snb [run]            discover, score, analyse, report   (default)
  snb doctor           check token, rate limits, profile and paths before a run
  snb dashboard        local web dashboard for past runs
  snb history          list runs / trends / triage status / --diff between runs
  snb profile-suggest  propose a profile from your own GitHub repos
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from . import __version__
from .config import Profile, load_env, read_profile_text
from .discovery import discover
from .explain import LLM, OpenAILLM, explain_all
from .github_api import GitHubClient, GitHubError, RateLimitError
from .graph import build_graph
from .graphql_api import BATCH_SIZE, fetch_users
from .history import History
from .models import Candidate, Recommendation
from .orgs import analyze_orgs
from .report import render_console, write_reports
from .scoring import apply_reputation, score_candidate

log = logging.getLogger(__name__)
DEFAULT_DB = "data/history.db"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Security engineer discovery and ranking")
    p.add_argument("--profile", default=None, help="profile YAML (default: ./profiles/security_profile.yaml, else the bundled one)")
    p.add_argument("--top", type=int, default=15, help="number of engineers in the report")
    p.add_argument("--min-score", type=float, default=0.0, help="drop engineers below this score")
    p.add_argument("--queries-per-domain", type=int, default=None, help="limit searches per domain (saves rate limit)")
    p.add_argument("--max-candidates", type=int, default=None, help="override settings.max_candidates")
    p.add_argument("--api", choices=["auto", "rest", "graphql"], default="auto", help="auto = GraphQL when a token is set")
    p.add_argument("--expand", type=int, default=0, metavar="N", help="also analyse contributors of the top N engineers' repos")
    p.add_argument("--ai", action="store_true", help="LLM explanations via AI_PROVIDER (openai or anthropic; sends public repo metadata)")
    p.add_argument("--history-db", default=DEFAULT_DB)
    p.add_argument("--no-history", action="store_true", help="do not record this run")
    p.add_argument("--include-ignored", action="store_true", help="keep engineers you marked 'ignored'")
    p.add_argument("--output-dir", default="reports")
    p.add_argument("--format", choices=["md", "json", "both"], default="both")
    p.add_argument("--no-report", action="store_true", help="print only, write no report files")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


# -- analysis steps --------------------------------------------------------
def _score_one(client: GitHubClient, cand: Candidate, profile: Profile, node: dict | None) -> Recommendation | None:
    if node:
        repos, stats = list(node["repos"]), node["stats"]
    else:
        repos, stats = client.list_user_repos(cand.login, profile.settings.max_repos_per_user), None
    # Seed repos come from search and carry the same fields, so merge them in.
    seen = {r.get("full_name") for r in repos}
    repos += [r for r in cand.seed_repos if r.get("full_name") not in seen]
    rec = score_candidate(cand.login, repos, profile, stats=stats)
    if rec:
        rec.via = cand.via
        if node:
            rec.profile, rec.orgs = node["profile"], list(stats.get("orgs", []))
    return rec


def analyse(client: GitHubClient, cands: list[Candidate], profile: Profile, api: str, min_score: float) -> list[Recommendation]:
    """Score candidates. On a rate limit, returns what was analysed so far."""
    recs: list[Recommendation] = []
    try:
        for i in range(0, len(cands), BATCH_SIZE if api == "graphql" else 1):
            batch = cands[i : i + (BATCH_SIZE if api == "graphql" else 1)]
            nodes: dict = {}
            if api == "graphql":
                try:
                    nodes = fetch_users(client, [c.login for c in batch], profile.settings.max_repos_per_user)
                except RateLimitError:
                    raise
                except GitHubError as exc:
                    log.warning("GraphQL batch failed (%s); falling back to REST", exc)
            for cand in batch:
                rec = _score_one(client, cand, profile, nodes.get(cand.login))
                if rec and rec.score >= min_score:
                    recs.append(rec)
    except RateLimitError as exc:
        print(f"Rate limit hit; continuing with {len(recs)} engineers analysed so far ({exc})\n", file=sys.stderr)
    except GitHubError as exc:
        print(f"GitHub error during analysis: {exc}", file=sys.stderr)
    return recs


def expand_contributors(client: GitHubClient, recs: list[Recommendation], profile: Profile, api: str, top_n: int, min_score: float, excluded: set[str]) -> tuple[dict[str, set[str]], list[Recommendation]]:
    """Contributor graph: who else works on the top engineers' repos? Returns (repo -> logins, new recs)."""
    co: dict[str, set[str]] = {}
    known = {r.login for r in recs}
    new: dict[str, Candidate] = {}
    try:
        for rec in recs[:top_n]:
            if not rec.matched_repos:
                continue
            repo = rec.matched_repos[0]["name"]
            logins = {c["login"] for c in client.list_contributors(repo, 15)}
            co[repo] = logins | {rec.login}
            for login in logins - known - excluded:
                new.setdefault(login, Candidate(login, f"https://github.com/{login}", via=f"contributor of {repo}"))
    except GitHubError as exc:
        print(f"Contributor expansion stopped early: {exc}", file=sys.stderr)
    extra = analyse(client, list(new.values())[:20], profile, api, min_score) if new else []
    return co, extra


def enrich_rest(client: GitHubClient, recs: list[Recommendation]) -> None:
    """REST mode: profile, followers and org memberships for the final list only."""
    try:
        for rec in recs:
            u = client.get_user(rec.login)
            rec.profile = {k: u.get(k) for k in ("name", "bio", "company", "location", "followers", "blog")}
            apply_reputation(rec, {"followers": u.get("followers", 0), "created_at": u.get("created_at")})
            rec.orgs = client.list_user_orgs(rec.login)
    except GitHubError:
        pass  # enrichment is optional


def run(args: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(levelname)s %(message)s")
    load_env()
    token = os.environ.get("GITHUB_TOKEN") or None
    api = args.api if args.api != "auto" else ("graphql" if token else "rest")
    if api == "graphql" and not token:
        print("--api graphql needs GITHUB_TOKEN (a token with no scopes is enough).", file=sys.stderr)
        return 1
    if not token:
        print("Warning: GITHUB_TOKEN not set. Anonymous limits are low (10 searches/min, 60 calls/hour) and GraphQL is unavailable.\n")

    llm = None
    if args.ai:
        provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
        llm = OpenAILLM.from_env() if provider == "openai" else LLM.from_env()
        required = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
        if not llm:
            print(f"Warning: --ai needs {required}; using offline explanations.\\n")

    profile = Profile.load(args.profile)
    client = GitHubClient(token)
    history = None if args.no_history else History(args.history_db)
    notes = history.statuses() if history else {}
    ignored = set() if args.include_ignored else {l for l, n in notes.items() if n["status"] == "ignored"}
    print(f"Building security network... [{api.upper()}]\n")

    try:
        candidates = discover(client, profile, args.queries_per_domain, progress=print)
    except RateLimitError as exc:
        print(f"Stopped during discovery: {exc}", file=sys.stderr)
        return 2
    except GitHubError as exc:
        print(f"GitHub error: {exc}", file=sys.stderr)
        return 1

    max_c = args.max_candidates or profile.settings.max_candidates
    ranked = [c for c in sorted(candidates.values(), key=lambda c: c.seed_weight, reverse=True) if c.login not in ignored][:max_c]
    print(f"Found {len(candidates)} engineers; analysing top {len(ranked)}...\n")

    recs = analyse(client, ranked, profile, api, args.min_score)
    recs.sort(key=lambda r: r.score, reverse=True)

    co: dict[str, set[str]] = {}
    if args.expand > 0 and recs:
        print(f"Expanding contributor graph around the top {args.expand} engineers...\n")
        excluded = ignored | {profile.github_username.lower()} if profile.github_username else set(ignored)
        co, extra = expand_contributors(client, recs, profile, api, args.expand, args.min_score, excluded)
        recs = sorted(recs + extra, key=lambda r: r.score, reverse=True)

    recs = recs[: args.top]
    if api == "rest":
        enrich_rest(client, recs)
        recs.sort(key=lambda r: r.score, reverse=True)

    # Phase 2/3/4 analysis on the final list
    graph = build_graph(recs, co)
    org_summary = analyze_orgs(recs)
    if history:
        seen, has_runs = history.seen_logins(), history.latest_run_id() is not None
        for rec in recs:
            rec.is_new = has_runs and rec.login not in seen
            rec.status = notes.get(rec.login, {}).get("status", "")
    explain_all(recs, llm)

    print(render_console(recs))
    if recs and not args.no_report:
        for path in write_reports(recs, args.output_dir, profile.name, args.format, graph.to_dict(), org_summary):
            print(f"Report written: {path}")
    if history and recs:
        run_id = history.save_run(recs, profile.name, api, graph.to_dict(), org_summary)
        print(f"Saved as run #{run_id}. View with: snb dashboard")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    command = argv[0] if argv and (not argv[0].startswith("-") or argv[0] == "--version") else "run"
    rest = argv[1:] if argv and not argv[0].startswith("-") else argv
    if command in ("--version", "version") or "--version" in argv[:1]:
        print(f"snb {__version__}")
        return 0
    if command == "doctor":
        from . import doctor
        return doctor.main(rest)
    if command == "dashboard":
        from . import dashboard
        return dashboard.main(rest)
    if command == "history":
        from . import history as history_cli
        return history_cli.main(rest)
    if command == "profile-suggest":
        return profile_suggest(rest)
    if command == "run":
        return run(parse_args(rest))
    print(f"Unknown command '{command}'. Use: run, dashboard, history, profile-suggest", file=sys.stderr)
    return 2


def profile_suggest(argv: list[str]) -> int:
    import yaml

    from .profile_builder import refine_with_llm, suggest_profile, to_yaml

    p = argparse.ArgumentParser(prog="main.py profile-suggest", description="Propose a profile from your public GitHub repos")
    p.add_argument("--github-user", required=True)
    p.add_argument("--base", default=None, help="taxonomy to start from (default: same resolution as --profile)")
    p.add_argument("--out", default="profiles/suggested_profile.yaml")
    p.add_argument("--ai", action="store_true", help="LLM refinement via AI_PROVIDER (sends your public repo metadata)")
    args = p.parse_args(argv)

    load_env()
    client = GitHubClient(os.environ.get("GITHUB_TOKEN") or None)
    try:
        repos = client.list_user_repos(args.github_user, 100)
    except GitHubError as exc:
        print(f"GitHub error: {exc}", file=sys.stderr)
        return 1
    if not repos:
        print(f"No public repositories found for {args.github_user}.")
        return 1
    base_dict = yaml.safe_load(read_profile_text(args.base))
    draft, notes = suggest_profile(args.github_user, repos, Profile.from_dict(base_dict), base_dict)
    if args.ai:
        provider = os.environ.get("AI_PROVIDER", "anthropic").lower()
        llm = OpenAILLM.from_env() if provider == "openai" else LLM.from_env()
        if llm:
            draft, note = refine_with_llm(llm, args.github_user, repos, draft)
            notes.append(note)
        else:
            required = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
            notes.append(f"--ai skipped: {required} not set.")
    Profile.from_dict(draft)  # never write an invalid profile
    Path(args.out).write_text(to_yaml(draft), encoding="utf-8")
    print("\n".join(f"- {n}" for n in notes))
    print(f"\nProfile written to {args.out}. Review it, then run: snb --profile {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
