from snb.watchlists import WatchlistStore

def test_watchlist_create_due_and_schedule():
    store = WatchlistStore(":memory:")
    item = store.create("Cloud security", "cloud security", min_score=10, domains=["cloud"], interval_minutes=15)
    assert item["enabled"] is True
    assert item["interval_minutes"] == 15
    assert item["domains"] == ["cloud"]
    # Force it due without relying on wall-clock timing.
    with store._conn() as db:
        db.execute("UPDATE watchlists SET next_run_at=?", ("2000-01-01T00:00:00+00:00",))
    due = store.due("2026-10-04T00:00:00+00:00")
    assert [x["id"] for x in due] == [item["id"]]
    scheduled = store.mark_scheduled(item["id"], now="2026-10-04T00:00:00+00:00")
    assert scheduled["last_run_at"] == "2026-10-04T00:00:00+00:00"
    assert scheduled["next_run_at"] == "2026-10-04T00:15:00+00:00"

def test_watchlist_enable_disable(tmp_path):
    store = WatchlistStore(tmp_path / "watchlists.db")
    item = store.create("Detection", "sigma", interval_minutes=60)
    assert store.set_enabled(item["id"], False)["enabled"] is False
    assert store.due("2099-01-01T00:00:00+00:00") == []
