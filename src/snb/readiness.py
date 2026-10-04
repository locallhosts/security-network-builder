from __future__ import annotations

import os
from pathlib import Path

from .history import History
from .jobs import JobQueue


def readiness() -> dict[str, object]:
    checks: dict[str, str] = {}
    try:
        History(os.environ.get("SNB_HISTORY_DB", "data/history.db"), database_url=os.environ.get("SNB_DATABASE_URL"))
        checks["history"] = "ok"
    except Exception:
        checks["history"] = "error"
    production = os.environ.get("SNB_ENV", "development").lower() == "production"
    checks["authentication"] = "ok" if (not production or os.environ.get("API_KEYS") or os.environ.get("API_KEY")) else "error"
    allowed_hosts = {h.strip() for h in os.environ.get("SNB_ALLOWED_HOSTS", "").split(",") if h.strip()}
    checks["trusted_hosts"] = "ok" if (not production or allowed_hosts) and "*" not in allowed_hosts else "error"
    history_path = os.environ.get("SNB_HISTORY_DB", "data/history.db")
    jobs_path = os.environ.get("SNB_JOBS_DB", "data/jobs.db")
    checks["data_path"] = "ok" if Path(history_path).parent.exists() else "error"
    try:
        JobQueue(jobs_path)
        checks["jobs"] = "ok"
    except Exception:
        checks["jobs"] = "error"

    provider = os.environ.get("AI_PROVIDER", "offline").strip().lower()
    if provider == "offline":
        checks["ai_provider"] = "ok"
    elif provider == "openai":
        checks["ai_provider"] = "ok" if os.environ.get("OPENAI_API_KEY") else "error"
    elif provider == "anthropic":
        checks["ai_provider"] = "ok" if os.environ.get("ANTHROPIC_API_KEY") else "error"
    else:
        checks["ai_provider"] = "error"

    return {"status": "ok" if all(v == "ok" for v in checks.values()) else "degraded", "checks": checks}
