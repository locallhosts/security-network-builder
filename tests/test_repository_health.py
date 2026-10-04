from datetime import datetime, timedelta, timezone

import pytest

from snb.repository_health import assess_repository


NOW = datetime(2026, 10, 4, tzinfo=timezone.utc)


def repo_at(days: int) -> dict:
    return {
        "full_name": "acme/project",
        "html_url": "https://github.com/acme/project",
        "pushed_at": (NOW - timedelta(days=days)).isoformat(),
        "license": {"spdx_id": "MIT"},
        "has_issues": True,
    }


def test_active_licensed_repository_is_healthy():
    result = assess_repository(repo_at(30), now=NOW)
    assert result["grade"] == "healthy"
    assert result["score"] >= 90
    assert any(x["id"] == "active" for x in result["signals"])


def test_archived_stale_repository_is_high_risk():
    repo = repo_at(1200)
    repo["archived"] = True
    repo["license"] = None
    result = assess_repository(repo, now=NOW)
    assert result["grade"] == "high-risk"
    assert result["score"] < 40
    assert {x["id"] for x in result["signals"]} >= {"archived", "stale"}


def test_missing_activity_is_unknown_not_stale():
    result = assess_repository({"full_name": "acme/unknown"}, now=NOW)
    assert result["activity_age_days"] is None
    assert "activity_unknown" in {x["id"] for x in result["signals"]}


def test_invalid_activity_is_unknown():
    result = assess_repository({"full_name": "acme/invalid", "pushed_at": "not-a-date"}, now=NOW)
    assert result["activity_age_days"] is None


@pytest.mark.parametrize(
    ("days", "expected_signal"),
    [(30, "active"), (180, "aging"), (800, "stale")],
)
def test_activity_bands(days, expected_signal):
    result = assess_repository(repo_at(days), now=NOW)
    assert expected_signal in {x["id"] for x in result["signals"]}
