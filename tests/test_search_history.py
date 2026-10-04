from snb.search_history import SearchHistoryStore


def repo(name, stars):
    return {
        "name": name.split("/")[-1],
        "full_name": name,
        "html_url": f"https://github.com/{name}",
        "owner": {"login": name.split("/")[0]},
        "stargazers_count": stars,
        "language": "Python",
    }


def test_search_history_compares_added_removed_and_moved(tmp_path):
    store = SearchHistoryStore(tmp_path / "searches.db")
    store.record("cloud", "cloud security", [repo("org/a", 10), repo("org/b", 5)], created_at="2026-10-01T00:00:00+00:00")
    store.record("cloud", "cloud security", [repo("org/b", 8), repo("org/c", 2)], created_at="2026-10-02T00:00:00+00:00")

    result = store.compare("cloud")
    assert result["added"][0]["full_name"] == "org/c"
    assert result["removed"][0]["full_name"] == "org/a"
    assert result["changed"][0]["repository"] == "org/b"
    assert result["changed"][0]["stars_delta"] == 3
    assert result["changed"][0]["rank_delta"] == 0


def test_search_history_is_bounded_and_deduplicates(tmp_path):
    store = SearchHistoryStore(tmp_path / "searches.db")
    duplicate = [repo("org/a", 1), repo("org/a", 2)]
    store.record("bounded", "security", duplicate)
    for i in range(25):
        store.record("bounded", "security", [repo(f"org/{i}", i)])
    snapshots = store.list("bounded")
    assert len(snapshots) == 20
    assert len(snapshots[0]["results"]) == 1
    assert snapshots[-1]["results"][0]["full_name"] == "org/5"


def test_search_history_validates_bounds(tmp_path):
    store = SearchHistoryStore(tmp_path / "searches.db")
    try:
        store.record("", "security", [])
        assert False
    except ValueError:
        pass
    try:
        store.list(limit=21)
        assert False
    except ValueError:
        pass
