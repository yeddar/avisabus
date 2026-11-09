"""`GET /api/v1/stops/{stop_id}/lines/{line}/position` over `gtfs_mini` and replayed SAE sessions
(position_estimation T-06).

`stop_508_peak` (Monday 2026-11-02, 20:42–21:07 in Madrid) has the 93 and the 70 at stop 508.
"""

import json
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text
from structlog.testing import capture_logs

from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalKind, ArrivalsSnapshot, SaeArrival
from avisabus.domain.services.occupancy_simulation import service_day_start
from avisabus.domain.services.position_estimator import estimate_position
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.position import position_client
from tests.support.sae import DERIVED_NO_ARRIVALS, STOP_508_PEAK
from tests.support.stops import API, CountingSource, import_feed, new_engine, replay, token

EARTH_RADIUS_M = 6_371_008.8
PROBLEM_JSON = "application/problem+json"
PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
POSITION_93 = f"{API}/stops/508/lines/93/position"
HEADSIGN_93 = "Passeig Marítim - Hospital Malva-rosa"
RESPONSE_FIELDS = {
    "stop",
    "line",
    "direction_id",
    "headsign",
    "source",
    "status",
    "generated_at",
    "refresh_after_s",
    "arrival",
    "vehicle",
    "shape_id",
    "position",
}


@pytest.fixture(scope="module")
def mini_engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    engine = new_engine(tmp_path_factory.mktemp("position") / "avisabus.sqlite")
    import_feed(engine, GTFS_MINI)
    yield engine
    engine.dispose()


@pytest.fixture
def repo(mini_engine: Engine) -> SqliteNetworkRepository:
    return SqliteNetworkRepository(mini_engine)


def _params(direction_id: int = 0, stop_id: str = "508") -> dict[str, Any]:
    return {"direction_id": direction_id, "t": token(stop_id)}


@dataclass
class StaticSource:
    """Arrivals source that always answers the same (or always fails)."""

    arrivals: tuple[SaeArrival, ...] = ()
    error: str | None = None
    calls: list[str] = field(default_factory=list)

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        self.calls.append(stop_id)
        if self.error is not None:
            raise ArrivalsUnavailableError(stop_id, self.error)
        return ArrivalsSnapshot(stop_id, datetime(2026, 11, 2, tzinfo=UTC), self.arrivals)


def _expected_estimate(
    repo: SqliteNetworkRepository, vehicle: dict[str, str], arrival_at: datetime, now: datetime
) -> Any:
    trip_id = vehicle["trip_id"]
    shape_id = repo.trip_shape_id(trip_id)
    assert shape_id is not None
    stop_times = repo.trip_stop_times(trip_id)
    names = {}
    for stop_time in stop_times:
        stop = repo.get_stop(stop_time.stop_id)
        assert stop is not None
        names[stop.stop_id] = stop.name
    service_date = datetime.fromisoformat(vehicle["service_date"]).date()
    return estimate_position(
        stop_times,
        repo.shape_points(shape_id),
        names,
        "508",
        service_day_start(service_date),
        arrival_at,
        now,
    )


# --- AC-06: distance_to_stop_m is measured in real metres ---


def _haversine_m(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Written here on purpose: the test must not depend on `domain.services.geometry`."""
    phi1, phi2 = math.radians(a[0]), math.radians(b[0])
    d_phi, d_lambda = phi2 - phi1, math.radians(b[1] - a[1])
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def _metres_along(shape: list[tuple[float, float]], point: tuple[float, float]) -> float:
    """Haversine length of the shape from its start to the point of the shape closest to `point`
    (on a plane tangent at `point`)."""
    cos_lat = math.cos(math.radians(point[0]))

    def plane(p: tuple[float, float]) -> tuple[float, float]:
        return (
            EARTH_RADIUS_M * math.radians(p[1] - point[1]) * cos_lat,
            EARTH_RADIUS_M * math.radians(p[0] - point[0]),
        )

    best_off, best_along, travelled = math.inf, 0.0, 0.0
    for a, b in zip(shape, shape[1:], strict=False):
        length = _haversine_m(a, b)
        (ax, ay), (bx, by) = plane(a), plane(b)
        dx, dy = bx - ax, by - ay
        length2 = dx * dx + dy * dy
        f = 0.0 if length2 == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / length2))
        off = math.hypot(ax + f * dx, ay + f * dy)
        if off < best_off:
            best_off, best_along = off, travelled + f * length
        travelled += length
    return best_along


@pytest.mark.spec("position_estimation.AC-06")
async def test_distance_to_the_stop_matches_the_length_measured_on_the_shape(
    mini_engine: Engine, repo: SqliteNetworkRepository
) -> None:
    """`shape_dist_traveled` of `gtfs_mini` is 2.7–3.4 times the real length of its shapes."""
    clock = FakeClock(PEAK_START)
    source, _ = replay(STOP_508_PEAK, clock)
    compared: list[int] = []
    async with position_client(mini_engine, clock, source) as (client, _):
        for _cycle in range(75):
            for line, direction_id in (("70", 1), ("93", 0)):
                response = await client.get(
                    f"{API}/stops/508/lines/{line}/position", params=_params(direction_id)
                )
                body = response.json()
                position = body["position"]
                if position is None or body["status"] == "AT_STOP":
                    continue
                shape = [(p.lat, p.lon) for p in repo.shape_points(body["shape_id"])]
                stop = (body["stop"]["lat"], body["stop"]["lon"])
                bus = (position["lat"], position["lon"])
                measured = _metres_along(shape, stop) - _metres_along(shape, bus)
                reported = position["distance_to_stop_m"]
                assert abs(reported - measured) < max(0.02 * measured, 10), (
                    body["vehicle"],
                    reported,
                    measured,
                )
                compared.append(reported)
            clock.advance(timedelta(seconds=20))
    assert len(compared) > 100
    assert max(compared) > 1000  # not only a few metres from the stop


# --- AC-09: contract, first arrival, same SAE cache ---


@pytest.mark.spec("position_estimation.AC-09")
async def test_position_of_the_first_arrival_of_the_line_and_direction(
    mini_engine: Engine, repo: SqliteNetworkRepository
) -> None:
    clock = FakeClock(PEAK_START)
    source, counting = replay(STOP_508_PEAK, clock)
    async with position_client(mini_engine, clock, source) as (client, _):
        arrivals = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
        stop = await client.get(f"{API}/stops/508", params={"t": token("508")})
        response = await client.get(POSITION_93, params=_params())
    assert counting.calls == 1  # the position reuses the arrivals' cached SAE answer
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    first = next(
        a for a in arrivals.json()["arrivals"] if a["line"] == "93" and a["direction_id"] == 0
    )
    assert first["vehicle"] is not None
    stop_508 = repo.get_stop("508")
    assert stop_508 is not None
    assert body["stop"] == {
        "stop_id": "508",
        "name": "Parc de l'Oest - Enguera",
        "lat": stop_508.lat,
        "lon": stop_508.lon,
    }
    headsign = next(
        line["headsign"]
        for line in stop.json()["lines"]
        if line["line"] == "93" and line["direction_id"] == 0
    )
    assert (body["line"], body["direction_id"], body["headsign"]) == ("93", 0, headsign)
    assert body["source"] == "REALTIME"
    assert body["generated_at"] == arrivals.json()["generated_at"]
    assert body["refresh_after_s"] == 20
    assert body["arrival"] == {
        key: first[key]
        for key in ("kind", "minutes", "arrival_at", "destination", "sae_destination")
    }
    assert body["arrival"]["destination"] == HEADSIGN_93
    assert body["vehicle"] == first["vehicle"]
    assert body["shape_id"] == repo.trip_shape_id(first["vehicle"]["trip_id"])
    expected = _expected_estimate(
        repo,
        first["vehicle"],
        datetime.fromisoformat(first["arrival_at"]),
        clock.now(),
    )
    assert body["status"] == expected.status.value
    assert body["position"] == {
        "lat": round(expected.lat, 6),
        "lon": round(expected.lon, 6),
        "bearing_deg": expected.bearing_deg,
        "distance_to_stop_m": round(expected.distance_to_stop_m),
        "stops_away": expected.stops_away,
        "next_stop": {"stop_id": expected.next_stop.stop_id, "name": expected.next_stop.name},
    }
    assert isinstance(body["position"]["distance_to_stop_m"], int)


@pytest.mark.spec("position_estimation.AC-09")
async def test_the_position_alone_asks_the_sae_once_and_shares_the_cache(
    mini_engine: Engine,
) -> None:
    clock = FakeClock(PEAK_START + timedelta(seconds=300))
    source, counting = replay(STOP_508_PEAK, clock)
    async with position_client(mini_engine, clock, source) as (client, _):
        for line, direction_id in (("93", 0), ("70", 1), ("93", 0)):
            response = await client.get(
                f"{API}/stops/508/lines/{line}/position", params=_params(direction_id)
            )
            assert response.status_code == 200
        await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
        assert counting.calls == 1
        clock.advance(timedelta(seconds=21))  # cache expired: one more request
        await client.get(POSITION_93, params=_params())
    assert counting.calls == 2


# --- AC-10: scheduled fallback ---


@pytest.mark.spec("position_estimation.AC-10")
async def test_scheduled_arrival_gives_the_position_on_the_timetable(
    mini_engine: Engine, repo: SqliteNetworkRepository
) -> None:
    clock = FakeClock(PEAK_START)
    source = CountingSource(StaticSource(error="timeout"))
    async with position_client(mini_engine, clock, source) as (client, _):
        response = await client.get(POSITION_93, params=_params())
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "SCHEDULED"
    assert body["arrival"]["kind"] == "CLOCK_TIME"
    assert body["arrival"]["sae_destination"] is None
    vehicle = body["vehicle"]
    # δ = 0: the arrival is the scheduled time of the trip at 508.
    at_508 = next(st for st in repo.trip_stop_times(vehicle["trip_id"]) if st.stop_id == "508")
    service_date = datetime.fromisoformat(vehicle["service_date"]).date()
    scheduled = service_day_start(service_date) + timedelta(seconds=at_508.arrival_s)
    assert datetime.fromisoformat(body["arrival"]["arrival_at"]) == scheduled
    expected = _expected_estimate(repo, vehicle, scheduled, clock.now())
    assert body["status"] == expected.status.value
    assert body["status"] in {"EN_ROUTE", "NOT_STARTED", "AT_STOP"}
    assert body["position"]["lat"] == round(expected.lat, 6)
    assert body["position"]["lon"] == round(expected.lon, 6)
    assert body["position"]["distance_to_stop_m"] == round(expected.distance_to_stop_m)


# --- AC-11: no arrival, no vehicle ---


@pytest.mark.spec("position_estimation.AC-11")
@pytest.mark.parametrize(("line", "direction_id"), [("93", 0), ("70", 1)])
async def test_without_arrivals_the_status_is_no_arrival(
    mini_engine: Engine, repo: SqliteNetworkRepository, line: str, direction_id: int
) -> None:
    clock = FakeClock(PEAK_START)
    source, _ = replay(DERIVED_NO_ARRIVALS, clock)  # stop 508 without any arrival
    async with position_client(mini_engine, clock, source) as (client, _):
        response = await client.get(
            f"{API}/stops/508/lines/{line}/position", params=_params(direction_id)
        )
    assert response.status_code == 200
    body = response.json()
    direction = repo.line_direction(line, direction_id)
    assert direction is not None
    assert body["status"] == "NO_ARRIVAL"
    assert body["source"] == "REALTIME"
    assert body["headsign"] == direction.headsign
    assert (body["arrival"], body["vehicle"], body["position"]) == (None, None, None)
    assert body["shape_id"] == direction.shape_id


@pytest.mark.spec("position_estimation.AC-11")
async def test_an_arrival_without_a_paired_trip_is_no_vehicle(
    mini_engine: Engine, repo: SqliteNetworkRepository
) -> None:
    now = datetime(2026, 11, 2, 2, 30, tzinfo=UTC)  # 03:30 in Madrid: no 93 trip around
    clock = FakeClock(now)
    arrival = SaeArrival("93", "Pass. Marítim", ArrivalKind.MINUTES, 5, now + timedelta(minutes=5))
    source = StaticSource(arrivals=(arrival,))
    async with position_client(mini_engine, clock, source) as (client, _):
        response = await client.get(POSITION_93, params=_params())
    assert response.status_code == 200
    body = response.json()
    direction = repo.line_direction("93", 0)
    assert direction is not None
    assert body["status"] == "NO_VEHICLE"
    assert body["arrival"]["minutes"] == 5
    assert body["arrival"]["sae_destination"] == "Pass. Marítim"
    assert (body["vehicle"], body["position"]) == (None, None)
    assert body["shape_id"] == direction.shape_id


@pytest.fixture
def own_engine(tmp_path: Path) -> Iterator[Engine]:
    """A `gtfs_mini` database of its own, for tests that alter the active network."""
    engine = new_engine(tmp_path / "avisabus.sqlite")
    import_feed(engine, GTFS_MINI)
    yield engine
    engine.dispose()


@pytest.mark.spec("position_estimation.AC-11")
async def test_a_position_that_cannot_be_estimated_is_no_vehicle_not_500(
    own_engine: Engine,
) -> None:
    # v1.2: the active network turns incoherent for the paired trip (stop times without
    # shape_dist_traveled and its first stop gone), as if the feed changed between requests.
    engine = own_engine
    repo = SqliteNetworkRepository(engine)
    clock = FakeClock(PEAK_START)
    source = CountingSource(StaticSource(error="timeout"))  # scheduled: always the same trip
    async with position_client(engine, clock, source) as (client, _):
        before = (await client.get(POSITION_93, params=_params())).json()
        assert before["position"] is not None
        trip_id = before["vehicle"]["trip_id"]
        first_stop = repo.trip_stop_times(trip_id)[0].stop_id
        assert first_stop != "508"
        with engine.begin() as conn:
            conn.execute(
                text("UPDATE gtfs_stop_time SET shape_dist = NULL WHERE trip_id = :trip_id"),
                {"trip_id": trip_id},
            )
            conn.execute(
                text("DELETE FROM gtfs_stop WHERE stop_id = :stop_id"), {"stop_id": first_stop}
            )
        with capture_logs() as logs:
            response = await client.get(POSITION_93, params=_params())
    assert response.status_code == 200
    body = response.json()
    assert set(body) == RESPONSE_FIELDS
    assert body["status"] == "NO_VEHICLE"
    assert body["position"] is None
    direction = repo.line_direction("93", 0)
    assert direction is not None
    assert body["shape_id"] == direction.shape_id  # the representative one, as with NO_VEHICLE
    assert body["vehicle"] == before["vehicle"]
    assert body["arrival"] == before["arrival"]
    failures = [log for log in logs if log["event"] == "position.estimate_failed"]
    assert failures == [
        {
            "event": "position.estimate_failed",
            "log_level": "warning",
            "trip_id": trip_id,
            "shape_id": repo.trip_shape_id(trip_id),
            "reason": "missing_stop_coordinates",
        }
    ]


# --- AC-12: errors ---


@pytest.mark.spec("position_estimation.AC-12")
async def test_invalid_token_or_unknown_stop_is_the_404_of_the_stops(mini_engine: Engine) -> None:
    clock = FakeClock(PEAK_START)
    source, counting = replay(STOP_508_PEAK, clock)
    requests = [
        (POSITION_93, {"direction_id": 0}),
        (POSITION_93, {"direction_id": 0, "t": "A" * 22}),
        (POSITION_93, {"direction_id": 0, "t": token("2070")}),
        (f"{API}/stops/999999/lines/93/position", {"direction_id": 0, "t": token("999999")}),
        (f"{API}/stops/508/lines/98/position", {"direction_id": 0, "t": "A" * 22}),
    ]
    async with position_client(mini_engine, clock, source) as (client, _):
        reference = await client.get(f"{API}/stops/508/arrivals", params={"t": "A" * 22})
        responses = [await client.get(url, params=params) for url, params in requests]
    assert reference.status_code == 404
    for response in responses:
        assert response.status_code == 404
        assert response.headers["content-type"].startswith(PROBLEM_JSON)
        assert response.headers["cache-control"] == "no-store"
        assert response.content == reference.content
    assert counting.calls == 0


@pytest.mark.spec("position_estimation.AC-12")
@pytest.mark.parametrize(("line", "direction_id"), [("98", 0), ("70", 0), ("93", 1), ("N4", 0)])
async def test_line_and_direction_not_at_the_stop_is_404(
    mini_engine: Engine, line: str, direction_id: int
) -> None:
    clock = FakeClock(PEAK_START)
    source, _ = replay(STOP_508_PEAK, clock)
    async with position_client(mini_engine, clock, source) as (client, _):
        response = await client.get(
            f"{API}/stops/508/lines/{line}/position", params=_params(direction_id)
        )
    assert response.status_code == 404
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "type": "https://avisabus/problems/line-not-at-stop",
        "title": "Not Found",
        "status": 404,
    }


async def test_position_without_an_active_feed_is_503(tmp_path: Path) -> None:
    engine = new_engine(tmp_path / "empty.sqlite")
    clock = FakeClock(PEAK_START)
    source, counting = replay(STOP_508_PEAK, clock)
    async with position_client(engine, clock, source) as (client, _):
        response = await client.get(POSITION_93, params=_params())
    engine.dispose()
    assert response.status_code == 503
    assert response.json()["type"] == "https://avisabus/problems/network-unavailable"
    assert counting.calls == 0


# --- AC-16: gzip ---


@pytest.mark.spec("position_estimation.AC-16")
async def test_position_responses_are_compressed_only_above_1_kb(mini_engine: Engine) -> None:
    clock = FakeClock(PEAK_START)
    source, _ = replay(STOP_508_PEAK, clock)
    async with position_client(mini_engine, clock, source) as (client, _):
        position = await client.get(
            POSITION_93, params=_params(), headers={"Accept-Encoding": "gzip"}
        )
        arrivals = await client.get(
            f"{API}/stops/508/arrivals",
            params={"t": token("508")},
            headers={"Accept-Encoding": "gzip"},
        )
    assert len(json.dumps(position.json()).encode()) < 1000
    assert "content-encoding" not in position.headers
    assert len(json.dumps(arrivals.json()).encode()) > 1000
    assert arrivals.headers["content-encoding"] == "gzip"
