from snb.jobs import JobQueue

def test_job_queue_idempotency_and_lifecycle():
    q = JobQueue(":memory:")
    first = q.enqueue("discovery", {"profile": "security"}, idempotency_key="abc")
    second = q.enqueue("discovery", {"profile": "security"}, idempotency_key="abc")
    assert first.id == second.id
    claimed = q.claim()
    assert claimed and claimed.attempts == 1
    q.succeed(claimed.id)
    assert q.get(first.id).status == "succeeded"

def test_job_retry_then_terminal_failure():
    q = JobQueue(":memory:")
    job = q.enqueue("discovery", {}, max_attempts=2)
    claimed = q.claim()
    assert claimed
    q.fail(claimed.id, "temporary", retry_delay=0)
    assert q.get(job.id).status == "queued"
    claimed = q.claim()
    assert claimed
    q.fail(claimed.id, "permanent", retry_delay=0)
    failed = q.get(job.id)
    assert failed.status == "failed"
    assert failed.attempts == 2

def test_worker_handles_missing_handler():
    q = JobQueue(":memory:")
    job = q.enqueue("unknown", {})
    result = q.run_once({})
    assert result and result.status == "queued"
    assert q.get(job.id).attempts == 1


def test_worker_persists_result():
    q = JobQueue(":memory:")
    job = q.enqueue("demo", {"x": 1})
    result = q.run_once({"demo": lambda payload: "completed"})
    assert result and result.status == "succeeded"
    assert q.get(job.id).result == "completed"


def test_job_queue_stats_are_bounded_and_do_not_expose_payload(tmp_path):
    from snb.jobs import JobQueue

    queue = JobQueue(tmp_path / "jobs.db")
    queue.enqueue("intelligence", {"secret": "do-not-return"})
    stats = queue.stats()
    assert stats["queued"] == 1
    assert stats["total"] == 1
    assert "secret" not in stats
