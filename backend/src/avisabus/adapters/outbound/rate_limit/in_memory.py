"""In-memory sliding-window `RateLimiter` (alert_create design §2, AC-08).

One deque of attempt instants per key, pruned lazily: when the key is used and, for every key, at
most once per window. Every attempt counts, admitted or not, until it leaves the window; `release`
removes the last one (a `200` of AC-07 does not count). The counters live only here, in memory,
and are never logged (RNF-06): keys carry a device hash or an IP address.
"""

import math
from collections import deque
from datetime import datetime, timedelta


class InMemoryRateLimiter:
    def __init__(self, limit: int, window: timedelta) -> None:
        if limit < 1:
            raise ValueError("the limit must be at least 1")
        if window <= timedelta(0):
            raise ValueError("the window must be positive")
        self._limit = limit
        self._window = window
        self._attempts: dict[str, deque[datetime]] = {}
        self._last_sweep: datetime | None = None

    @property
    def tracked_keys(self) -> int:
        """Keys with some attempt in memory."""
        return len(self._attempts)

    def acquire(self, key: str, now: datetime) -> int | None:
        self._sweep(now)
        attempts = self._attempts.setdefault(key, deque())
        self._prune(attempts, now)
        attempts.append(now)
        excess = len(attempts) - self._limit
        if excess <= 0:
            return None
        # The next attempt is admitted once only `limit - 1` attempts remain in the window, that
        # is, once the first `excess + 1` (this one included in the count) have left it.
        room_at = attempts[excess] + self._window
        return max(1, math.ceil((room_at - now).total_seconds()))

    def release(self, key: str, now: datetime) -> None:
        attempts = self._attempts.get(key)
        if attempts is None:
            return
        self._prune(attempts, now)
        if attempts:
            attempts.pop()
        if not attempts:
            del self._attempts[key]

    def _prune(self, attempts: deque[datetime], now: datetime) -> None:
        """Drop the attempts that left the window `(now − window, now]`."""
        while attempts and attempts[0] <= now - self._window:
            attempts.popleft()

    def _sweep(self, now: datetime) -> None:
        """Forget the keys without attempts in the window, at most once per window."""
        if self._last_sweep is not None and now - self._last_sweep < self._window:
            return
        self._last_sweep = now
        for key in list(self._attempts):
            attempts = self._attempts[key]
            self._prune(attempts, now)
            if not attempts:
                del self._attempts[key]
