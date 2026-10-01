import pytest

from snb import history
from snb.history import History
from snb.models import Recommendation


def rec(login, score):
    return Recommendation(login, "u", score, ["eBPF"], {}, [], [])


def test_save_and_read_run(tmp_path):
    h = History(tmp_path / "h.db")
    rid = h.save_run([rec("a", 10), rec("b", 20)], "P", "rest", {"nodes": []}, [{"login": "o"}])
    data = h.get_run(rid)
    assert [r["login"] for r in data["recommendations"]] == ["b", "a"]     # score order
    assert data["organizations"] == [{"login": "o"}] and h.latest_run_id() == rid
    assert h.runs()[0]["count"] == 2 and h.get_run(999) is None


def test_trend_and_seen(tmp_path):
    h = History(tmp_path / "h.db")
    h.save_run([rec("a", 10)], "P", "rest", {}, [])
    h.save_run([rec("a", 14), rec("b", 5)], "P", "rest", {}, [])
    assert [x["score"] for x in h.engineer_history("a")] == [10, 14]
    assert h.seen_logins() == {"a", "b"}


def test_status_roundtrip_and_validation(tmp_path):
    h = History(tmp_path / "h.db")
    h.set_status("a", "reviewing", "check the eBPF repo")
    assert h.statuses()["a"]["note"] == "check the eBPF repo"
    h.set_status("a", "connected")
    assert h.statuses()["a"]["status"] == "connected"
    h.set_status("a", "")
    assert h.statuses() == {}
    with pytest.raises(ValueError):
        h.set_status("a", "followed")


def test_sql_injection_is_inert(tmp_path):
    h = History(tmp_path / "h.db")
    h.set_status("x'); DROP TABLE notes;--", "ignored")
    assert "x'); DROP TABLE notes;--" in h.statuses()


def test_history_cli(tmp_path, capsys):
    db = str(tmp_path / "h.db")
    History(db).save_run([rec("alice", 12)], "P", "rest", {}, [])
    assert history.main(["--db", db]) == 0 and "1 engineers" in capsys.readouterr().out
    assert history.main(["--db", db, "--set", "alice", "ignored"]) == 0
    assert history.main(["--db", db, "--set", "alice", "bogus"]) == 1
    assert history.main(["--db", db, "--login", "alice"]) == 0 and "score 12" in capsys.readouterr().out
