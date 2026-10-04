"""Background worker entry points for durable intelligence jobs."""
from __future__ import annotations

import os
from typing import Any

from .intelligence import build_provider, recommendation_payload
from .jobs import JobQueue
from .models import Recommendation


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


def handlers() -> dict[str, Any]:
    return {"intelligence": intelligence_handler}


def run_worker(*, jobs_db: str = "data/jobs.db", max_jobs: int = 1) -> list[Any]:
    return JobQueue(jobs_db).run(handlers(), max_jobs=max_jobs)
