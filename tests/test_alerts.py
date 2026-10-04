from snb.alerts import changes_since_previous_run
from snb.history import History
from snb.models import Recommendation

def rec(login: str, score: float) -> Recommendation:
    return Recommendation(login, f"https://github.com/{login}", score, [], {}, [], [])

def test_change_alerts_are_deterministic(tmp_path):
    h = History(tmp_path / "history.db")
    h.save_run([rec("alice", 10), rec("bob", 8)], "p", "rest", {}, [])
    h.save_run([rec("alice", 15), rec("carol", 9)], "p", "rest", {}, [])
    result = changes_since_previous_run(h, min_move=2)
    assert result["run"] == 2
    assert {a["type"] for a in result["alerts"]} == {"new_engineer", "dropped_engineer", "score_change"}
    assert any(a["login"] == "alice" and a["delta"] == 5 for a in result["alerts"])
