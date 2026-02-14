from __future__ import annotations

import time
from collections import defaultdict


class InMemoryRateLimiter:
    def __init__(self, max_requests: int = 10, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._events: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        events = [t for t in self._events[key] if t >= cutoff]
        self._events[key] = events
        if len(events) >= self.max_requests:
            return False
        events.append(now)
        self._events[key] = events
        return True


capture_rate_limiter = InMemoryRateLimiter(max_requests=15, window_seconds=60)
