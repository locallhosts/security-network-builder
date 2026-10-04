"""Bounded in-process rate limiting for the public HTTP API.

The limiter is deliberately process-local: it is a last-mile abuse control, not a
replacement for a shared edge/WAF limiter. State is bounded so attacker-controlled
client identifiers cannot grow memory without limit.
"""
from __future__ import annotations

import time
from collections import OrderedDict, deque
from dataclasses import dataclass
from math import ceil
from threading import Lock


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int
    reset_after: int


class SlidingWindowLimiter:
    def __init__(self, *, max_clients: int = 5000) -> None:
        self.max_clients = max_clients
        self._hits: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, key: str, *, limit: int, window: float, now: float | None = None) -> RateLimitDecision:
        if limit < 1 or window <= 0:
            raise ValueError("rate-limit configuration must be positive")
        now = time.monotonic() if now is None else now
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = deque()
                self._hits[key] = hits
            else:
                self._hits.move_to_end(key)
            while hits and now - hits[0] >= window:
                hits.popleft()

            if len(hits) >= limit:
                retry = max(1, ceil(window - (now - hits[0])))
                return RateLimitDecision(False, limit, 0, retry, retry)

            hits.append(now)
            if len(self._hits) > self.max_clients:
                self._hits.popitem(last=False)
            reset = max(1, ceil(window - (now - hits[0])))
            return RateLimitDecision(True, limit, max(0, limit - len(hits)), 0, reset)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()
