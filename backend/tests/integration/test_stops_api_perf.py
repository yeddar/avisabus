"""p95 of `/arrivals` with the SAE answer in cache (stop_arrivals_api AC-17). Slow and manual:

    cd backend && uv run pytest -m slow tests/integration/test_stops_api_perf.py -s

Measured on the development machine; the result is noted in `progress/impl_stop_arrivals_api.md`
(the 500 ms target on the Raspberry Pi is checked in `nfr_validation`).
"""

import statistics
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine

from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import STOP_508_PEAK
from tests.support.stops import API, import_feed, new_engine, replay, stops_client, token

pytestmark = pytest.mark.slow

REQUESTS = 200
P95_LIMIT_MS = 100
PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)


@pytest.fixture
def mini_engine(tmp_path: Path) -> Iterator[Engine]:
    engine = new_engine(tmp_path / "avisabus.sqlite")
    import_feed(engine, GTFS_MINI)
    yield engine
    engine.dispose()


@pytest.mark.spec("stop_arrivals_api.AC-17")
@pytest.mark.parametrize("stop_id", ["508", "2070"])
async def test_p95_of_cached_arrivals_is_below_100_ms(mini_engine: Engine, stop_id: str) -> None:
    clock = FakeClock(PEAK_START)
    source, counting = replay(STOP_508_PEAK, clock)
    params = {"t": token(stop_id)}
    async with stops_client(mini_engine, clock, source) as (client, _):
        await client.get(f"{API}/stops/{stop_id}/arrivals", params=params)  # fills the cache
        times_ms = []
        for _ in range(REQUESTS):
            started = time.perf_counter()
            response = await client.get(f"{API}/stops/{stop_id}/arrivals", params=params)
            times_ms.append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200
    p95 = statistics.quantiles(times_ms, n=20)[-1]
    print(
        f"\nAC-17 stop {stop_id}: {REQUESTS} cached requests, median "
        f"{statistics.median(times_ms):.1f} ms, p95 {p95:.1f} ms, max {max(times_ms):.1f} ms"
    )
    assert counting.calls == 1
    assert p95 < P95_LIMIT_MS
