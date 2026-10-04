from snb.audit import AuditLog


def test_audit_events_are_bounded_and_ordered(tmp_path):
    log = AuditLog(str(tmp_path / "audit.db"))
    log.record("auth.private", outcome="rejected", detail="bad key")
    log.record("job.created", subject="job-1")
    rows = log.recent()
    assert [r["event"] for r in rows] == ["job.created", "auth.private"]
    assert len(rows[1]["detail"]) <= 500


def test_audit_limit_is_bounded():
    log = AuditLog(":memory:")
    for i in range(5):
        log.record("event", subject=str(i))
    assert len(log.recent(2)) == 2


def test_ai_explanation_audit_metadata_contains_no_secret(tmp_path, monkeypatch):
    from snb.explain import explain_all
    from snb.models import Recommendation

    class FakeLLM:
        def explain(self, recommendation):
            return "safe explanation"

    recommendation = Recommendation(
        login="alice",
        url="https://github.com/alice",
        score=1,
        matched_domains=["Cloud"],
        breakdown={},
        evidence=[],
        matched_repos=[],
    )
    audit = AuditLog(str(tmp_path / "audit.db"))
    explain_all([recommendation], FakeLLM(), audit)
    assert recommendation.explanation_source == "ai"
    assert recommendation.explanation_provider == "anthropic"
    event = audit.recent(1)[0]
    assert event["event"] == "ai.explanation"
    assert "api_key" not in event["detail"].lower()
