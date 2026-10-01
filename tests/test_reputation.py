from datetime import datetime, timezone

from conftest import repo
from snb.reputation import REPUTATION_CAP, compute_reputation
from snb.scoring import apply_reputation, score_candidate

NOW = datetime(2026, 9, 15, tzinfo=timezone.utc)


def test_empty_stats_give_nothing():
    assert compute_reputation({}, NOW) == (0.0, "")


def test_all_signals_and_cap():
    pts, line = compute_reputation(
        {"followers": 5000, "commits": 900, "pull_requests": 100, "reviews": 50, "created_at": "2015-01-01T00:00:00Z"}, NOW)
    assert pts == REPUTATION_CAP == 6.0
    assert "followers" in line and "code reviews" in line


def test_followers_alone_cannot_dominate():
    pts, _ = compute_reputation({"followers": 10_000_000}, NOW)
    assert pts == 2


def test_apply_reputation_is_idempotent(profile):
    rec = score_candidate("a", [repo("x", "ebpf")], profile, NOW)
    base = rec.score
    stats = {"followers": 200, "commits": 600}
    apply_reputation(rec, stats, NOW)
    once = rec.score
    apply_reputation(rec, stats, NOW)
    assert rec.score == once > base
    assert sum(e.startswith("Reputation:") for e in rec.evidence) == 1
