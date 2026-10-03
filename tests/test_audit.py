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
