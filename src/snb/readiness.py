from __future__ import annotations

import os
from pathlib import Path

from .history import History


def readiness() -> dict[str, object]:
    checks: dict[str, str] = {}
    try:
        History(os.environ.get("SNB_HISTORY_DB", "data/history.db"), database_url=os.environ.get("SNB_DATABASE_URL"))
        checks["history"] = "ok"
    except Exception:
        checks["history"] = "error"
    production = os.environ.get("SNB_ENV", "development").lower() == "production"
    checks["authentication"] = "ok" if (not production or os.environ.get("API_KEYS") or os.environ.get("API_KEY")) else "error"
    checks["data_path"] = "ok" if Path(os.environ.get("SNB_HISTORY_DB", "data/history.db")).parent.exists() else "error"
    return {"status": "ok" if all(v == "ok" for v in checks.values()) else "degraded", "checks": checks}
