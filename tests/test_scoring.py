from datetime import datetime, timezone

from conftest import repo
from scoring import score_candidate

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_no_match_returns_none(profile):
    assert score_candidate("a", [repo("todo-app", "a todo list")], profile, NOW) is None


def test_single_domain_score_and_evidence(profile):
    rec = score_candidate("alice", [repo("tracer", "eBPF runtime tracer", stars=0)], profile, NOW)
    assert rec.breakdown["eBPF"] == 10
    assert rec.breakdown["Recent activity"] == 3       # pushed 14 days earlier
    assert rec.score == 13
    assert "eBPF" in rec.matched_domains
    assert any("alice/tracer" in e for e in rec.evidence)


def test_multi_domain_beats_single(profile):
    single = score_candidate("a", [repo("x", "ebpf thing")], profile, NOW)
    multi = score_candidate("a", [repo("x", "ebpf thing"), repo("y", "sigma rules")], profile, NOW)
    assert multi.score > single.score
    assert set(multi.matched_domains) == {"eBPF", "Detection"}


def test_extra_repos_capped(profile):
    repos = [repo(f"r{i}", "ebpf") for i in range(10)]
    rec = score_candidate("a", repos, profile, NOW)
    assert rec.breakdown["eBPF"] == 13                  # 10 + cap of 3


def test_forks_and_archived_ignored(profile):
    repos = [repo("a", "ebpf", fork=True), repo("b", "ebpf", archived=True)]
    assert score_candidate("a", repos, profile, NOW) is None


def test_stale_repo_gets_no_activity_bonus(profile):
    rec = score_candidate("a", [repo("x", "ebpf", pushed="2024-01-01T00:00:00Z")], profile, NOW)
    assert "Recent activity" not in rec.breakdown


def test_traction_is_capped(profile):
    rec = score_candidate("a", [repo("x", "ebpf", stars=1_000_000)], profile, NOW)
    assert rec.breakdown["Community traction"] == 3


def test_preferred_language_bonus(profile):
    rec = score_candidate("a", [repo("x", "ebpf", lang="Go")], profile, NOW)
    assert rec.breakdown["Preferred language"] == 1
