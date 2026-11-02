"""`CachedArrivalsSource`: TTL, single-flight, negative cache, concurrency and stats (T-05)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from structlog.testing import capture_logs

from avisabus.adapters.outbound.sae.cache import CachedArrivalsSource, CacheStats
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalsSnapshot
from tests.support.fake_clock import FakeClock

NOW = datetime(2026, 11, 2, 11, 0, tzinfo=UTC)


class FakeSource:
    """Counts calls per stop; can fail and can hold every call until `release` is set."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.calls: list[str] = []
        self.failing: set[str] = set()
        self.release: asyncio.Event | None = None
        self.in_flight = 0
        self.max_in_flight = 0

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        self.calls.append(stop_id)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.release is not None:
                await self.release.wait()
            if stop_id in self.failing:
                raise ArrivalsUnavailableError(stop_id, "timeout")
            return ArrivalsSnapshot(stop_id, self.clock.now(), ())
        finally:
            self.in_flight -= 1


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture
def inner(clock: FakeClock) -> FakeSource:
    return FakeSource(clock)


def _cache(
    inner: FakeSource,
    clock: FakeClock,
    *,
    ttl_s: float = 20,
    error_ttl_s: float = 5,
    max_concurrency: int = 4,
) -> CachedArrivalsSource:
    return CachedArrivalsSource(
        inner=inner,
        clock=clock,
        ttl=timedelta(seconds=ttl_s),
        error_ttl=timedelta(seconds=error_ttl_s),
        max_concurrency=max_concurrency,
    )


async def _settle() -> None:
    """Let every ready task run until it blocks."""
    for _ in range(5):
        await asyncio.sleep(0)


# --- AC-09 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-09")
async def test_fresh_snapshot_is_served_from_cache(inner: FakeSource, clock: FakeClock) -> None:
    cache = _cache(inner, clock)
    first = await cache.get_arrivals("508")
    clock.advance(timedelta(seconds=19.9))
    assert await cache.get_arrivals("508") is first
    assert inner.calls == ["508"]


@pytest.mark.spec("sae_arrivals_source.AC-09")
async def test_snapshot_as_old_as_the_ttl_is_fetched_again(
    inner: FakeSource, clock: FakeClock
) -> None:
    cache = _cache(inner, clock)
    first = await cache.get_arrivals("508")
    clock.advance(timedelta(seconds=20))
    second = await cache.get_arrivals("508")
    assert second is not first
    assert second.fetched_at == NOW + timedelta(seconds=20)
    assert inner.calls == ["508", "508"]


@pytest.mark.spec("sae_arrivals_source.AC-09")
async def test_ttl_is_per_stop_and_configurable(inner: FakeSource, clock: FakeClock) -> None:
    cache = _cache(inner, clock, ttl_s=60)
    await cache.get_arrivals("508")
    await cache.get_arrivals("2070")
    clock.advance(timedelta(seconds=59))
    await cache.get_arrivals("508")
    await cache.get_arrivals("2070")
    assert inner.calls == ["508", "2070"]


# --- AC-10 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-10")
async def test_concurrent_requests_share_one_fetch_and_result(
    inner: FakeSource, clock: FakeClock
) -> None:
    cache = _cache(inner, clock)
    inner.release = asyncio.Event()
    pending = asyncio.gather(*(cache.get_arrivals("508") for _ in range(5)))
    await _settle()
    assert inner.calls == ["508"]
    inner.release.set()
    results = await pending
    assert inner.calls == ["508"]
    assert all(result is results[0] for result in results)


@pytest.mark.spec("sae_arrivals_source.AC-10")
async def test_concurrent_requests_share_the_same_error(
    inner: FakeSource, clock: FakeClock
) -> None:
    cache = _cache(inner, clock)
    inner.release = asyncio.Event()
    inner.failing.add("508")
    pending = asyncio.gather(*(cache.get_arrivals("508") for _ in range(3)), return_exceptions=True)
    await _settle()
    inner.release.set()
    errors = await pending
    assert inner.calls == ["508"]
    assert all(isinstance(error, ArrivalsUnavailableError) for error in errors)
    assert all(error is errors[0] for error in errors)


@pytest.mark.spec("sae_arrivals_source.AC-10")
async def test_cancelling_one_caller_does_not_cancel_the_shared_fetch(
    inner: FakeSource, clock: FakeClock
) -> None:
    cache = _cache(inner, clock)
    inner.release = asyncio.Event()
    first = asyncio.create_task(cache.get_arrivals("508"))
    second = asyncio.create_task(cache.get_arrivals("508"))
    await _settle()
    first.cancel()
    await _settle()
    inner.release.set()
    snapshot = await second
    assert snapshot.stop_id == "508"
    assert first.cancelled()
    assert inner.calls == ["508"]


# --- AC-11 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-11")
async def test_failure_is_cached_for_the_error_ttl(inner: FakeSource, clock: FakeClock) -> None:
    cache = _cache(inner, clock)
    inner.failing.add("508")
    with pytest.raises(ArrivalsUnavailableError) as first:
        await cache.get_arrivals("508")
    clock.advance(timedelta(seconds=4.9))
    with pytest.raises(ArrivalsUnavailableError) as second:
        await cache.get_arrivals("508")
    assert second.value is first.value
    assert inner.calls == ["508"]

    clock.advance(timedelta(seconds=0.1))  # 5 s after the failure
    inner.failing.clear()
    assert (await cache.get_arrivals("508")).stop_id == "508"
    assert inner.calls == ["508", "508"]


@pytest.mark.spec("sae_arrivals_source.AC-11")
async def test_error_ttl_is_configurable(inner: FakeSource, clock: FakeClock) -> None:
    cache = _cache(inner, clock, error_ttl_s=30)
    inner.failing.add("508")
    for _ in range(3):
        with pytest.raises(ArrivalsUnavailableError):
            await cache.get_arrivals("508")
        clock.advance(timedelta(seconds=10))
    assert inner.calls == ["508"]


@pytest.mark.spec("sae_arrivals_source.AC-11")
async def test_failure_of_one_stop_does_not_affect_another(
    inner: FakeSource, clock: FakeClock
) -> None:
    cache = _cache(inner, clock)
    inner.failing.add("508")
    with pytest.raises(ArrivalsUnavailableError):
        await cache.get_arrivals("508")
    assert (await cache.get_arrivals("2070")).stop_id == "2070"


# --- AC-12 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-12")
@pytest.mark.parametrize("limit", [4, 2])
async def test_simultaneous_fetches_are_limited_across_stops(
    inner: FakeSource, clock: FakeClock, limit: int
) -> None:
    cache = _cache(inner, clock, max_concurrency=limit)
    inner.release = asyncio.Event()
    stops = [str(n) for n in range(10)]
    pending = asyncio.gather(*(cache.get_arrivals(stop) for stop in stops))
    await _settle()
    assert inner.in_flight == limit
    inner.release.set()
    results = await pending
    assert [r.stop_id for r in results] == stops
    assert inner.max_in_flight == limit
    assert sorted(inner.calls) == sorted(stops)


# --- AC-13 -------------------------------------------------------------------------------------


@pytest.mark.spec("sae_arrivals_source.AC-13")
async def test_counts_hits_misses_and_source_errors(inner: FakeSource, clock: FakeClock) -> None:
    cache = _cache(inner, clock)
    assert cache.stats() == CacheStats(hits=0, misses=0, errors=0)
    await cache.get_arrivals("508")  # miss
    await cache.get_arrivals("508")  # hit
    inner.failing.add("2070")
    with pytest.raises(ArrivalsUnavailableError):
        await cache.get_arrivals("2070")  # miss + source error
    with pytest.raises(ArrivalsUnavailableError):
        await cache.get_arrivals("2070")  # hit (negative cache)
    assert cache.stats() == CacheStats(hits=2, misses=2, errors=1)


@pytest.mark.spec("sae_arrivals_source.AC-13")
async def test_emit_stats_logs_the_counters(inner: FakeSource, clock: FakeClock) -> None:
    cache = _cache(inner, clock)
    await cache.get_arrivals("508")
    await cache.get_arrivals("508")
    with capture_logs() as logs:
        cache.emit_stats()
    assert logs == [
        {"event": "sae.stats", "log_level": "info", "hits": 1, "misses": 1, "errors": 0}
    ]
