"""C1 terminals with the real feed (`data/gtfs/emt/`, not versioned). Slow and manual:

    cd backend && uv run pytest -m slow tests/integration/test_stops_api_real_feed.py -s

`gtfs_mini` has no C1, so the generic SAE text "Cntr.Històric" at its terminals 1959 and 2277
(real answers of E-03, `samples/day_2026-11-03`) is checked over the full feed (AC-19). Skipped
when the feed is not present.
"""

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine
from structlog.testing import capture_logs

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from tests.support.fake_clock import FakeClock
from tests.support.sae import DAY
from tests.support.stops import API, import_feed, new_engine, replay, stops_client, token

REAL_FEED = Path(__file__).resolve().parents[3] / "data" / "gtfs" / "emt"
DAY_START = datetime(2026, 11, 3, 8, 59, 0, 733841, tzinfo=UTC)

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(not (REAL_FEED / "stop_times.txt").is_file(), reason="no real feed"),
]


@pytest.fixture(scope="module")
def real_engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    engine = new_engine(tmp_path_factory.mktemp("real") / "avisabus.sqlite")
    import_feed(engine, REAL_FEED)
    yield engine
    engine.dispose()


@pytest.mark.spec("stop_arrivals_api.AC-19")
@pytest.mark.parametrize(
    ("stop_id", "captured", "direction_id", "headsign"),
    [
        ("1959", "08:59:02", 0, "Xàtiva - Institut Lluís Vives"),
        ("2277", "08:59:23", 1, "Blanqueria - Pare d'Òrfens"),
    ],
)
async def test_c1_generic_destination_at_its_terminals_is_the_departing_direction(
    real_engine: Engine, stop_id: str, captured: str, direction_id: int, headsign: str
) -> None:
    clock = FakeClock(datetime.fromisoformat(f"2026-11-03T{captured}+00:00"))
    source, _ = replay(DAY, clock, start=DAY_START)
    repo = SqliteNetworkRepository(real_engine)
    assert {h.direction_id for h in repo.headsigns_at_stop(stop_id, "C1")} == {0, 1}
    with capture_logs() as logs:
        async with stops_client(real_engine, clock, source) as (client, _):
            response = await client.get(
                f"{API}/stops/{stop_id}/arrivals", params={"t": token(stop_id)}
            )
    arrivals = response.json()["arrivals"]
    c1 = [a for a in arrivals if a["line"] == "C1"]
    assert len(c1) == 2
    for arrival in c1:
        assert arrival["sae_destination"] == "Cntr.Històric"
        assert (arrival["direction_id"], arrival["destination"]) == (direction_id, headsign)
        assert arrival["can_alert"] is True
        assert arrival["vehicle"] is not None
        assert repo.trip_stop_times(arrival["vehicle"]["trip_id"])[0].stop_id == stop_id
    # Every line of these terminals that is in the network gets a direction.
    assert all(a["direction_id"] is not None for a in arrivals if a["in_network"])
    assert not [log for log in logs if log["event"] == "arrivals.direction_unresolved"]
