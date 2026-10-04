"""Background worker entry points for durable intelligence jobs."""
from __future__ import annotations

import os
from typing import Any

from .intelligence import build_provider, recommendation_payload
from .jobs import JobQueue
from .models import Recommendation
from .watchlist_runner import build_watchlist_payload, run_watchlist
from .watchlists import WatchlistStore


def _recommendation(payload: dict[str, Any]) -> Recommendation:
    return Recommendation(
        login=str(payload["login"]),
        url=f"https://github.com/{payload['login']}",
        score=float(payload.get("score", 0)),
        matched_domains=list(payload.get("matched_domains", [])),
        breakdown={str(k): float(v) for k, v in payload.get("breakdown", {}).items()},
        evidence=list(payload.get("evidence", [])),
        matched_repos=list(payload.get("repositories", [])),
    )


def intelligence_handler(payload: dict[str, Any]) -> str:
    provider = build_provider(
        os.environ.get("AI_PROVIDER", "offline"),
        anthropic_key=os.environ.get("ANTHROPIC_API_KEY"),
        openai_key=os.environ.get("OPENAI_API_KEY"),
        anthropic_model=os.environ.get("ANTHROPIC_MODEL"),
        openai_model=os.environ.get("OPENAI_MODEL"),
    )
    # The payload is already sanitized by recommendation_payload().
    recommendation = _recommendation(payload)
    return provider.explain(recommendation)


def watchlist_handler(payload: dict[str, Any]) -> str:
    """Execute one queued watchlist using the normal history store."""
    return run_watchlist(payload)


def handlers() -> dict[str, Any]:
    return {"intelligence": intelligence_handler, "watchlist": watchlist_handler}


def enqueue_due_watchlists(
    *,
    watchlists_db: str = "data/watchlists.db",
    jobs_db: str = "data/jobs.db",
    history_db: str = "data/history.db",
) -> list[Any]:
    """Queue each currently-due watchlist exactly once for its schedule slot."""
    store = WatchlistStore(watchlists_db)
    queue = JobQueue(jobs_db)
    queued = []
    for item in store.due():
        slot = str(item["next_run_at"])
        key = f"watchlist:{item['id']}:{slot}"
        job = queue.enqueue(
            "watchlist",
            build_watchlist_payload(item, history_db=history_db),
            idempotency_key=key,
        )
        # Advancing the schedule at enqueue time makes the scheduler idempotent:
        # repeated scheduler ticks cannot create another job for this slot.
        store.mark_scheduled(item["id"])
        queued.append(job)
    return queued


def run_worker(
    *,
    jobs_db: str = "data/jobs.db",
    max_jobs: int = 1,
    enqueue_due: bool = False,
    watchlists_db: str = "data/watchlists.db",
    history_db: str = "data/history.db",
) -> list[Any]:
    if enqueue_due:
        enqueue_due_watchlists(
            watchlists_db=watchlists_db,
            jobs_db=jobs_db,
            history_db=history_db,
        )
    return JobQueue(jobs_db).run(handlers(), max_jobs=max_jobs)
