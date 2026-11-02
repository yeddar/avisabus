"""Per-stop cache in front of an `ArrivalsSource` (sae_arrivals_source design §3, RNF-08).

- A snapshot younger than `ttl` is served without asking the source (AC-09).
- Concurrent requests for the same stop share a single fetch: the fetch runs in its own task
  that every caller awaits (shielded, so cancelling one caller does not cancel it) (AC-10).
- A failure is cached for `error_ttl` and the same error is raised again (AC-11).
- At most `max_concurrency` fetches run at once, adding up every stop (AC-12).
- Hits, misses and source errors are counted; `emit_stats` logs `sae.stats` (AC-13).
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

import structlog

from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalsSnapshot
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock

log = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CacheStats:
    hits: int
    """Requests answered from a stored snapshot or error."""
    misses: int
    """Requests without a valid stored entry (they start or join a fetch)."""
    errors: int
    """Fetches that failed."""


@dataclass(frozen=True, slots=True)
class _Entry:
    stored_at: datetime
    snapshot: ArrivalsSnapshot | None
    error: ArrivalsUnavailableError | None


class CachedArrivalsSource:
    def __init__(
        self,
        inner: ArrivalsSource,
        clock: Clock,
        ttl: timedelta,
        error_ttl: timedelta,
        max_concurrency: int,
    ) -> None:
        self._inner = inner
        self._clock = clock
        self._ttl = ttl
        self._error_ttl = error_ttl
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._entries: dict[str, _Entry] = {}
        self._in_flight: dict[str, asyncio.Task[ArrivalsSnapshot]] = {}
        self._hits = 0
        self._misses = 0
        self._errors = 0

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        entry = self._entries.get(stop_id)
        if entry is not None and self._is_fresh(entry):
            self._hits += 1
            if entry.error is not None:
                raise entry.error
            assert entry.snapshot is not None  # noqa: S101 - one of the two is always set
            return entry.snapshot
        self._misses += 1
        task = self._in_flight.get(stop_id)
        if task is None:
            task = asyncio.create_task(self._fetch(stop_id))
            self._in_flight[stop_id] = task
            task.add_done_callback(lambda done: self._forget(stop_id, done))
        return await asyncio.shield(task)

    def stats(self) -> CacheStats:
        return CacheStats(hits=self._hits, misses=self._misses, errors=self._errors)

    def emit_stats(self) -> None:
        """Log `sae.stats` with the counters accumulated since start-up."""
        stats = self.stats()
        log.info("sae.stats", hits=stats.hits, misses=stats.misses, errors=stats.errors)

    def _is_fresh(self, entry: _Entry) -> bool:
        age = self._clock.now() - entry.stored_at
        return age < (self._ttl if entry.error is None else self._error_ttl)

    async def _fetch(self, stop_id: str) -> ArrivalsSnapshot:
        try:
            async with self._semaphore:
                snapshot = await self._inner.get_arrivals(stop_id)
        except ArrivalsUnavailableError as error:
            self._errors += 1
            self._entries[stop_id] = _Entry(self._clock.now(), None, error)
            raise
        except Exception:
            self._errors += 1
            raise
        self._entries[stop_id] = _Entry(self._clock.now(), snapshot, None)
        return snapshot

    def _forget(self, stop_id: str, done: "asyncio.Task[ArrivalsSnapshot]") -> None:
        if self._in_flight.get(stop_id) is done:
            del self._in_flight[stop_id]
        if not done.cancelled():
            done.exception()  # retrieved here so an unawaited failure is not reported as lost
