"""Spend and traffic guards: a daily spend tracker, a per-key rate limiter, a request deadline.

All clocks are injectable. Every class is thread-safe: the API serves requests from a pool.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, date, datetime

MAX_TRACKED_KEYS = 10_000
WINDOW_S = 60.0


def utc_now() -> datetime:
    """Return the current time, UTC."""
    return datetime.now(UTC)


class DailyBudget:
    """In-process spend counter in USD, reset at 00:00 UTC (design: generation.md)."""

    def __init__(self, limit_usd: float, now: Callable[[], datetime] = utc_now) -> None:
        self.limit_usd = limit_usd
        self._now = now
        self._lock = threading.Lock()
        self._day: date = now().astimezone(UTC).date()
        self._spent = 0.0

    def _roll(self) -> None:
        today = self._now().astimezone(UTC).date()
        if today != self._day:
            self._day = today
            self._spent = 0.0

    @property
    def spent_usd(self) -> float:
        """Spend since 00:00 UTC."""
        with self._lock:
            self._roll()
            return self._spent

    def exhausted(self) -> bool:
        """Whether the day's budget is spent."""
        return self.spent_usd >= self.limit_usd

    def add(self, cost_usd: float) -> None:
        """Record a cost."""
        with self._lock:
            self._roll()
            self._spent += max(cost_usd, 0.0)


class RateLimiter:
    """Sliding one-minute window per key, with a computable `Retry-After`."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.per_minute = per_minute
        self._clock = clock
        self._lock = threading.Lock()
        self._hits: dict[str, deque[float]] = {}

    def _prune(self, now: float) -> None:
        stale = [k for k, w in self._hits.items() if not w or w[-1] <= now - WINDOW_S]
        for key in stale:
            del self._hits[key]

    def acquire(self, key: str) -> float:
        """Take one slot: 0.0 when allowed, else the seconds to wait before a slot frees up."""
        now = self._clock()
        with self._lock:
            if len(self._hits) > MAX_TRACKED_KEYS:
                self._prune(now)
            window = self._hits.setdefault(key, deque())
            while window and window[0] <= now - WINDOW_S:
                window.popleft()
            if len(window) >= self.per_minute:
                return max(window[0] + WINDOW_S - now, 0.001)
            window.append(now)
            return 0.0


class Deadline:
    """A time budget for one request, counted from creation."""

    def __init__(self, total_s: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._end = clock() + total_s

    def remaining(self) -> float:
        """Seconds left (may be negative)."""
        return self._end - self._clock()

    def expired(self) -> bool:
        """Whether the budget is spent."""
        return self.remaining() <= 0
