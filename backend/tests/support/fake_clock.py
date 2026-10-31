"""Deterministic clock for tests (never used in production code)."""

from datetime import UTC, datetime, timedelta


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("FakeClock requires a timezone-aware datetime")
    return value.astimezone(UTC)


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = _require_aware(start)

    def now(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta

    def set(self, value: datetime) -> None:
        self._now = _require_aware(value)
