"""Small GitHub REST client: public data only, rate-limit aware, read-only."""
from __future__ import annotations

import logging
import time
from typing import Any

import requests

log = logging.getLogger(__name__)

API = "https://api.github.com"


class GitHubError(Exception):
    pass


class NotFoundError(GitHubError):
    pass


class RateLimitError(GitHubError):
    pass


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        session: requests.Session | None = None,
        max_retries: int = 3,
        max_wait: int = 120,
        sleep=time.sleep,
    ) -> None:
        self.token = token
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "security-network-builder",
            }
        )
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.max_retries = max_retries
        self.max_wait = max_wait
        self._sleep = sleep
        self._last_search = 0.0

    # -- internals -----------------------------------------------------
    @staticmethod
    def _is_rate_limited(resp: requests.Response) -> bool:
        if resp.status_code == 429:
            return True
        if resp.status_code != 403:
            return False
        return (
            resp.headers.get("X-RateLimit-Remaining") == "0"
            or "Retry-After" in resp.headers
            or "rate limit" in resp.text.lower()
        )

    @staticmethod
    def _wait_seconds(resp: requests.Response) -> float:
        if "Retry-After" in resp.headers:
            return float(resp.headers["Retry-After"]) + 1
        reset = resp.headers.get("X-RateLimit-Reset")
        if reset:
            return max(0.0, float(reset) - time.time()) + 1
        return 60.0

    def _request(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{API}{path}"
        for attempt in range(self.max_retries + 1):
            resp = self.session.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                raise NotFoundError(path)
            if self._is_rate_limited(resp):
                wait = self._wait_seconds(resp)
                if wait > self.max_wait or attempt == self.max_retries:
                    raise RateLimitError(f"rate limited; reset in ~{int(wait)}s (set GITHUB_TOKEN for higher limits)")
                log.warning("Rate limited, sleeping %.0fs", wait)
                self._sleep(wait)
                continue
            if 500 <= resp.status_code < 600 and attempt < self.max_retries:
                self._sleep(2**attempt)
                continue
            raise GitHubError(f"{resp.status_code} for {path}: {resp.text[:200]}")
        raise GitHubError(f"exhausted retries for {path}")

    def _throttle_search(self) -> None:
        # Search API: 30 req/min authenticated, 10 req/min anonymous.
        interval = 2.1 if self.token else 6.5
        elapsed = time.monotonic() - self._last_search
        if elapsed < interval:
            self._sleep(interval - elapsed)
        self._last_search = time.monotonic()

    # -- public API ----------------------------------------------------
    def search_repositories(self, query: str, per_page: int = 30, sort: str = "stars") -> list[dict[str, Any]]:
        self._throttle_search()
        data = self._request(
            "/search/repositories",
            {"q": query, "sort": sort, "order": "desc", "per_page": min(per_page, 100)},
        )
        return data.get("items", [])

    def list_user_repos(self, login: str, limit: int = 100) -> list[dict[str, Any]]:
        try:
            return self._request(
                f"/users/{login}/repos",
                {"type": "owner", "sort": "pushed", "per_page": min(limit, 100)},
            )
        except NotFoundError:
            return []

    def get_user(self, login: str) -> dict[str, Any]:
        try:
            return self._request(f"/users/{login}")
        except NotFoundError:
            return {}
