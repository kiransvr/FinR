from __future__ import annotations

from collections import defaultdict, deque
from threading import Lock
import time


class SlidingWindowRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self._limit = limit
        self._window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self._window_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= self._limit:
                return False

            bucket.append(now)
            return True
