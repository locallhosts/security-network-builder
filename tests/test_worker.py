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


def test_due_watchlist_is_enqueued_once(tmp_path):
    from snb.watchlists import WatchlistStore
    from snb.worker import enqueue_due_watchlists

    watchlists = WatchlistStore(tmp_path / "watchlists.db")
    item = watchlists.create("Cloud", "cloud security", interval_minutes=15)
    with watchlists._conn() as db:
        db.execute("UPDATE watchlists SET next_run_at=?", ("2000-01-01T00:00:00+00:00",))

    jobs_db = tmp_path / "jobs.db"
    first = enqueue_due_watchlists(
        watchlists_db=str(tmp_path / "watchlists.db"),
        jobs_db=str(jobs_db),
        history_db=str(tmp_path / "history.db"),
    )
    second = enqueue_due_watchlists(
        watchlists_db=str(tmp_path / "watchlists.db"),
        jobs_db=str(jobs_db),
        history_db=str(tmp_path / "history.db"),
    )

    assert len(first) == 1
    assert second == []
    assert watchlists.due("2026-10-04T00:00:00+00:00") == []


def test_watchlist_worker_persists_run(tmp_path):
    from snb.history import History
    from snb.watchlist_runner import run_watchlist

    class FakeGitHub:
        def search_repositories(self, query, per_page=30):
            assert "cloud security" in query
            return [{
                "full_name": "alice/cloud-security",
                "name": "cloud-security",
                "description": "cloud security automation",
                "html_url": "https://github.com/alice/cloud-security",
                "stargazers_count": 10,
                "language": "Python",
                "pushed_at": "2026-09-20T00:00:00Z",
                "archived": False,
                "fork": False,
                "owner": {"login": "alice", "type": "User", "html_url": "https://github.com/alice"},
            }]

    history = History(tmp_path / "history.db")
    result = run_watchlist(
        {
            "watchlist_id": "wl-1",
            "query": "cloud security",
            "min_score": 0,
            "history_db": str(tmp_path / "history.db"),
        },
        client=FakeGitHub(),
        history=history,
    )
    assert result.startswith("watchlist run 1:")
    assert history.latest_run_id() == 1
    assert history.get_run(1)["recommendations"][0]["login"] == "alice"
