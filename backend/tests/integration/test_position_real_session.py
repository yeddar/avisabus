"""Estimated positions over the real session `stop_508_peak` (position_estimation T-07, AC-17).

The whole session (75 cycles, 20 s apart) is replayed with `gtfs_mini`, asking the position API for
every line and direction of stop 508 (93 towards Passeig Marítim, 70 towards Alboraia) at each
cycle, with the `FakeClock` advanced 20 s between cycles. The properties are checked on every
estimated position:

- every REALTIME position is less than 30 m from the shape of its trip;
- for the same trip, between two successive observations in which the SAE minutes of that
  arrival do not increase, the distance to the stop does not grow more than 50 m. Pairs in which
  the SAE delays the arrival are excluded (spec v1.1: the bus may then go back) and reported.

Distances to the shape are measured here with a local equirectangular projection, independently
of `avisabus.domain.services.geometry`.
"""

import asyncio
import math
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.position import position_client
from tests.support.sae import STOP_508_PEAK
from tests.support.stops import API, import_feed, new_engine, replay, token

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
CYCLES = 75
STEP = timedelta(seconds=20)
MAX_OFF_SHAPE_M = 30
MAX_DISTANCE_GROWTH_M = 50
EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class Observation:
    cycle: int
    line: str
    trip_id: str
    source: str
    status: str
    minutes: int | None
    lat: float
    lon: float
    distance_to_stop_m: int
    shape_id: str


@dataclass(frozen=True)
class Session:
    observations: list[Observation]
    lines_at_stop: list[tuple[str, int]]
    shapes: dict[str, list[tuple[float, float]]]
    sae_requests: int


@pytest.fixture(scope="module")
def mini_engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    engine = new_engine(tmp_path_factory.mktemp("real_session") / "avisabus.sqlite")
    import_feed(engine, GTFS_MINI)
    yield engine
    engine.dispose()


async def _replay_session(engine: Engine) -> Session:
    repo = SqliteNetworkRepository(engine)
    lines = [(d.line, d.direction_id) for d in repo.lines_at_stop("508")]
    clock = FakeClock(PEAK_START)
    source, counting = replay(STOP_508_PEAK, clock)
    observations = []
    async with position_client(engine, clock, source) as (client, _):
        for cycle in range(CYCLES):
            for line, direction_id in lines:
                response = await client.get(
                    f"{API}/stops/508/lines/{line}/position",
                    params={"direction_id": direction_id, "t": token("508")},
                )
                assert response.status_code == 200
                body = response.json()
                if body["position"] is None:
                    continue
                observations.append(
                    Observation(
                        cycle=cycle,
                        line=line,
                        trip_id=body["vehicle"]["trip_id"],
                        source=body["source"],
                        status=body["status"],
                        minutes=body["arrival"]["minutes"],
                        lat=body["position"]["lat"],
                        lon=body["position"]["lon"],
                        distance_to_stop_m=body["position"]["distance_to_stop_m"],
                        shape_id=body["shape_id"],
                    )
                )
            clock.advance(STEP)
    shapes = {
        shape_id: [(p.lat, p.lon) for p in repo.shape_points(shape_id)]
        for shape_id in {o.shape_id for o in observations}
    }
    return Session(observations, lines, shapes, counting.calls)


@pytest.fixture(scope="module")
def session(mini_engine: Engine) -> Session:
    return asyncio.run(_replay_session(mini_engine))


def _distance_to_shape_m(lat: float, lon: float, shape: list[tuple[float, float]]) -> float:
    """Minimum distance from the point to the polyline, on a plane tangent at the point."""
    cos_lat = math.cos(math.radians(lat))

    def plane(point: tuple[float, float]) -> tuple[float, float]:
        return (
            EARTH_RADIUS_M * math.radians(point[1] - lon) * cos_lat,
            EARTH_RADIUS_M * math.radians(point[0] - lat),
        )

    best = math.inf
    vertices = [plane(p) for p in shape]
    for (ax, ay), (bx, by) in zip(vertices, vertices[1:], strict=False):
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        f = 0.0 if length2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length2))
        best = min(best, math.hypot(ax + f * dx, ay + f * dy))
    return best


def _successive_pairs(session: Session) -> list[tuple[Observation, Observation]]:
    """Successive observations of the same trip (of the same line), in replay order."""
    last: dict[tuple[str, str], Observation] = {}
    pairs = []
    for observation in session.observations:
        key = (observation.line, observation.trip_id)
        if key in last:
            pairs.append((last[key], observation))
        last[key] = observation
    return pairs


@pytest.mark.spec("position_estimation.AC-17")
def test_the_whole_session_is_replayed_with_realtime_positions(session: Session) -> None:
    assert session.lines_at_stop == [("70", 1), ("93", 0)]
    assert session.sae_requests == CYCLES  # one SAE answer per cycle, shared by both lines
    assert {o.source for o in session.observations} == {"REALTIME"}
    # Both lines have a position at almost every cycle, over several trips and states.
    for line in ("70", "93"):
        cycles = {o.cycle for o in session.observations if o.line == line}
        assert len(cycles) == CYCLES
        assert len({o.trip_id for o in session.observations if o.line == line}) >= 3
    assert {o.status for o in session.observations} >= {"EN_ROUTE", "AT_STOP"}


@pytest.mark.spec("position_estimation.AC-17")
def test_every_realtime_position_is_on_the_shape_of_its_trip(session: Session) -> None:
    for o in session.observations:
        off_shape = _distance_to_shape_m(o.lat, o.lon, session.shapes[o.shape_id])
        assert off_shape < MAX_OFF_SHAPE_M, (o, off_shape)


@pytest.mark.spec("position_estimation.AC-17")
def test_distance_to_the_stop_does_not_grow_while_the_sae_minutes_do_not_increase(
    session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    checked, excluded = [], []
    for before, after in _successive_pairs(session):
        assert before.minutes is not None
        assert after.minutes is not None
        (excluded if after.minutes > before.minutes else checked).append((before, after))
    for before, after in checked:
        growth = after.distance_to_stop_m - before.distance_to_stop_m
        assert growth <= MAX_DISTANCE_GROWTH_M, (before, after)
    with capsys.disabled():
        print(
            f"\nAC-17: {len(checked)} pairs checked, {len(excluded)} excluded because the SAE "
            "minutes increased: "
            + ", ".join(
                f"{b.line} {b.trip_id} cycles {b.cycle}->{a.cycle} "
                f"min {b.minutes}->{a.minutes} d {b.distance_to_stop_m}->{a.distance_to_stop_m}"
                for b, a in excluded
            )
        )
    assert len(checked) > 100
    # The excluded pairs are the ones where the estimated bus went back (spec v1.1, AC-17).
    assert excluded
    assert all(
        a.distance_to_stop_m - b.distance_to_stop_m > MAX_DISTANCE_GROWTH_M for b, a in excluded
    )
