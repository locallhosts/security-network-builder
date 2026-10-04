"""Deterministic change detection and alert generation."""
from __future__ import annotations

from typing import Any

from .history import History

def changes_since_previous_run(history: History, run_id: int | None = None,
                               *, min_move: float = 2.0) -> dict[str, Any]:
    current = run_id or history.latest_run_id()
    if current is None:
        return {"base": None, "run": None, "new": [], "dropped": [], "movers": [], "alerts": []}
    base = history.previous_run_id(current)
    if base is None:
        return {"base": None, "run": current, "new": [], "dropped": [], "movers": [], "alerts": []}
    diff = history.diff_runs(base, current, min_move=min_move)
    if diff is None:
        return {"base": base, "run": current, "new": [], "dropped": [], "movers": [], "alerts": []}
    alerts: list[dict[str, Any]] = []
    for item in diff["new"]:
        alerts.append({"type": "new_engineer", "login": item["login"], "score": item["score"]})
    for item in diff["dropped"]:
        alerts.append({"type": "dropped_engineer", "login": item["login"], "score": item["score"]})
    for item in diff["movers"]:
        alerts.append({
            "type": "score_change",
            "login": item["login"],
            "from": item["from"],
            "to": item["to"],
            "delta": item["delta"],
        })
    return {**diff, "alerts": alerts}
