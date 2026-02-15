from __future__ import annotations

import threading
import time
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Small in-memory TTL cache for MCP call-path acceleration."""

    def __init__(self, ttl_seconds: int = 60, max_entries: int = 512) -> None:
        self._ttl_seconds = max(1, ttl_seconds)
        self._max_entries = max(16, max_entries)
        self._data: dict[str, tuple[float, T]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> T | None:
        now = time.time()
        with self._lock:
            value = self._data.get(key)
            if value is None:
                return None
            expires_at, payload = value
            if expires_at <= now:
                self._data.pop(key, None)
                return None
            return payload

    def set(self, key: str, value: T) -> None:
        now = time.time()
        with self._lock:
            self._evict_expired_locked(now)
            if len(self._data) >= self._max_entries:
                oldest_key = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest_key, None)
            self._data[key] = (now + self._ttl_seconds, value)

    def get_or_set(self, key: str, factory: Callable[[], T]) -> tuple[T, bool]:
        cached = self.get(key)
        if cached is not None:
            return cached, True
        value = factory()
        self.set(key, value)
        return value, False

    def _evict_expired_locked(self, now: float) -> None:
        expired = [k for k, (expires_at, _) in self._data.items() if expires_at <= now]
        for key in expired:
            self._data.pop(key, None)
