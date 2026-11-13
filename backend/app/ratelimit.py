"""Simple in-memory rate limits for public endpoints.

Each limiter allows `limit` hits per key within a sliding `window` of seconds.
Counts live in this process's memory: fine for one backend instance (as on
Northflank today). With several instances each would count separately, and a
shared store (Redis) would be needed for exact limits.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

from fastapi import HTTPException, status

# Forget keys that haven't been seen for a while once there are this many.
_MAX_KEYS = 10_000


class RateLimiter:
    def __init__(self, limit: int, window: float, clock: Callable[[], float] = time.monotonic):
        self.limit = limit
        self.window = window
        self.clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> float | None:
        """Counts one hit. Returns None if allowed, else the seconds until the next one is."""
        now = self.clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                return max(hits[0] + self.window - now, 1.0)
            hits.append(now)
            if len(self._hits) > _MAX_KEYS:
                self._forget_idle(now)
            return None

    def _forget_idle(self, now: float) -> None:
        for key in [k for k, h in self._hits.items() if not h or h[-1] <= now - self.window]:
            del self._hits[key]

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def enforce(limiter: RateLimiter, key: str, message: str) -> None:
    """Raises 429 with Retry-After when the key is over its limit."""
    wait = limiter.hit(key)
    if wait is not None:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, message, headers={"Retry-After": str(int(wait + 0.999))}
        )
