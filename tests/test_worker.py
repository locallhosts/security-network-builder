from snb.worker import intelligence_handler


def test_intelligence_worker_offline():
    payload = {
        "login": "alice",
        "score": 12,
        "matched_domains": ["Cloud"],
        "breakdown": {"Cloud": 12},
        "evidence": ["repo"],
        "repositories": [{"name": "alice/tool", "stars": 4, "language": "Go", "description": "security"}],
    }
    result = intelligence_handler(payload)
    assert result.startswith("@alice scored")


def test_worker_rejects_missing_login():
    try:
        intelligence_handler({})
        assert False
    except KeyError:
        pass
