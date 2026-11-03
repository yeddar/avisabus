"""`GetVehiclePosition` over `GetStopArrivals` with fakes of every port (position_estimation T-04).

The 93 trip `93_122` reaches stop 508 at 19:50:35 UTC; its stops S1, S2, 508 and S4 are at 0,
1200, 2400 and 3600 m of a straight northbound shape, 6 min, 2 min, 0 and 3 min after/before.
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

import pytest

from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.application.get_vehicle_position import GetVehiclePosition, VehiclePosition
from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from avisabus.domain.errors import (
    ArrivalsUnavailableError,
    LineNotAtStopError,
    NoActiveFeedError,
    StopNotFoundError,
)
from avisabus.domain.models.arrivals import ArrivalKind, ArrivalsSnapshot, SaeArrival
from avisabus.domain.models.network import ShapePoint, Stop, TripStopTime
from avisabus.domain.models.occupancy import OccupancyReading, OccupancyThresholds, VehicleRef
from avisabus.domain.models.position import PositionStatus, StopRef
from avisabus.domain.models.stop_arrivals import ArrivalSource, VehicleView
from avisabus.domain.services.direction_resolver import DEFAULT_ALIASES
from avisabus.domain.services.geometry import EARTH_RADIUS_M, haversine_m
from avisabus.domain.services.occupancy_simulation import service_day_start
from tests.support.fake_clock import FakeClock
from tests.support.network import FakeNetwork, FakeStopTokenSigner, line_direction

NOW = datetime(2026, 11, 2, 19, 48, 3, tzinfo=UTC)
DAY = date(2026, 11, 2)
SCHEDULED_508 = datetime(2026, 11, 2, 19, 50, 35, tzinfo=UTC)
SIGNER = FakeStopTokenSigner()
TOKEN = SIGNER.sign("508")
HEADSIGN_93 = "Passeig Marítim - Hospital Malva-rosa"
LAT0, LON0 = 39.45, -0.38


def _north(d_m: float) -> tuple[float, float]:
    return LAT0 + math.degrees(d_m / EARTH_RADIUS_M), LON0


@dataclass
class FakeArrivalsSource:
    arrivals: tuple[SaeArrival, ...] = ()
    error: str | None = None
    calls: list[str] = field(default_factory=list)

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        self.calls.append(stop_id)
        if self.error is not None:
            raise ArrivalsUnavailableError(stop_id, self.error)
        return ArrivalsSnapshot(stop_id=stop_id, fetched_at=NOW, arrivals=self.arrivals)


class NoOccupancy:
    async def read(self, vehicle: VehicleRef, at: datetime) -> OccupancyReading | None:
        return None


class SilentLogger:
    def debug(self, event: str, **fields: object) -> None: ...

    def info(self, event: str, **fields: object) -> None: ...

    def warning(self, event: str, **fields: object) -> None: ...


@dataclass
class World:
    network: FakeNetwork
    source: FakeArrivalsSource
    clock: FakeClock

    def use_case(self) -> GetVehiclePosition:
        stop_arrivals = GetStopArrivals(
            network=self.network,
            signer=SIGNER,
            arrivals=self.source,
            scheduled=ScheduledArrivalsProvider(self.network),
            occupancy=NoOccupancy(),
            thresholds=OccupancyThresholds(),
            clock=self.clock,
            refresh_after_s=20,
            match_tolerance=timedelta(minutes=10),
            aliases=DEFAULT_ALIASES,
            direction_overrides={},
            min_score=0.2,
            logger=SilentLogger(),
        )
        return GetVehiclePosition(stop_arrivals, self.network, self.clock)

    async def execute(
        self, line: str = "93", direction_id: int = 0, stop_id: str = "508", token: str = TOKEN
    ) -> VehiclePosition:
        return await self.use_case().execute(stop_id, token, line, direction_id)


def _sae(line: str, destination: str, minutes: int) -> SaeArrival:
    return SaeArrival(
        line, destination, ArrivalKind.MINUTES, minutes, NOW + timedelta(minutes=minutes)
    )


@pytest.fixture
def world() -> World:
    network = FakeNetwork()
    network.add_line("93", "1E90FF", "FFFFFF")
    network.add_line("70")
    network.add_stop(
        "508",
        "Parc de l'Oest - Enguera",
        line_direction("70", 1, "Alboraia"),
        line_direction("93", 0, HEADSIGN_93),
    )
    network.add_headsign("508", "93", 0, HEADSIGN_93)
    network.add_headsign("508", "70", 1, "Alboraia")
    for stop_id, d in (("S1", 0), ("S2", 1200), ("S4", 3600)):
        lat, lon = _north(d)
        network.stops[stop_id] = Stop(stop_id, f"Stop {stop_id}", lat, lon)
    network.add_passage("508", "93_122", "93", 0, HEADSIGN_93, SCHEDULED_508, DAY)
    network.add_passage(
        "508", "93_123", "93", 0, HEADSIGN_93, SCHEDULED_508 + timedelta(minutes=9), DAY
    )
    at_508 = int((SCHEDULED_508 - service_day_start(DAY)).total_seconds())
    network.trips["93_122"] = [
        TripStopTime("S1", 1, at_508 - 360, at_508 - 360, 0.0),
        TripStopTime("S2", 2, at_508 - 120, at_508 - 120, 1200.0),
        TripStopTime("508", 3, at_508, at_508, 2400.0),
        TripStopTime("S4", 4, at_508 + 180, at_508 + 180, 3600.0),
    ]
    network.trip_shapes["93_122"] = "shape_93_trip"
    network.shapes["shape_93_trip"] = [
        ShapePoint(*_north(d), n + 1, float(d)) for n, d in enumerate(range(0, 3601, 300))
    ]
    return World(network, FakeArrivalsSource(), FakeClock(NOW))


def _assert_at(position: VehiclePosition, d_m: float) -> None:
    assert position.estimate is not None
    assert position.estimate.shape_distance_m == pytest.approx(d_m)
    assert haversine_m(position.estimate.lat, position.estimate.lon, *_north(d_m)) < 1


@pytest.mark.spec("position_estimation.AC-09")
async def test_position_of_the_first_arrival_of_the_line_and_direction(world: World) -> None:
    world.source.arrivals = (
        _sae("93", "Pass. Marítim", 13),
        _sae("70", "Alboraia", 1),
        _sae("93", "Pass. Marítim", 4),  # 19:52:03: 88 s late for 93_122
    )
    position = await world.execute()
    assert world.source.calls == ["508"]  # the same single request as the arrivals
    assert position.stop == world.network.stops["508"]
    assert (position.line, position.direction_id, position.headsign) == ("93", 0, HEADSIGN_93)
    assert position.source is ArrivalSource.REALTIME
    assert position.generated_at == NOW
    assert position.refresh_after_s == 20
    assert position.arrival is not None
    assert position.arrival.minutes == 4
    assert position.arrival.arrival_at == NOW + timedelta(minutes=4)
    assert position.arrival.destination == HEADSIGN_93
    assert position.arrival.sae_destination == "Pass. Marítim"
    assert position.arrival.vehicle == VehicleView("93_122", DAY)
    assert position.shape_id == "shape_93_trip"
    assert position.status is PositionStatus.EN_ROUTE
    # Shifted instant: 19:48:03 − 88 s = 4 min before 508, halfway between S1 and S2.
    _assert_at(position, 600)
    assert position.estimate is not None
    assert position.estimate.distance_to_stop_m == pytest.approx(1800)
    assert position.estimate.stops_away == 1
    assert position.estimate.next_stop == StopRef("S2", "Stop S2")
    assert position.estimate.bearing_deg == pytest.approx(0.0, abs=0.01)


@pytest.mark.spec("position_estimation.AC-09")
@pytest.mark.spec("position_estimation.AC-03")
async def test_an_arrival_of_0_minutes_is_at_the_stop(world: World) -> None:
    world.source.arrivals = (_sae("93", "Pass. Marítim", 0),)
    position = await world.execute()
    assert position.status is PositionStatus.AT_STOP
    _assert_at(position, 2400)
    assert position.estimate is not None
    assert position.estimate.next_stop == StopRef("508", "Parc de l'Oest - Enguera")


@pytest.mark.spec("position_estimation.AC-10")
async def test_scheduled_arrivals_give_the_position_on_the_timetable(world: World) -> None:
    world.source.error = "timeout"
    position = await world.execute()
    assert position.source is ArrivalSource.SCHEDULED
    assert position.arrival is not None
    assert position.arrival.arrival_at == SCHEDULED_508
    assert position.arrival.sae_destination is None
    assert position.status is PositionStatus.EN_ROUTE
    # δ = 0: 152 s before 508, between S1 (−360 s) and S2 (−120 s).
    _assert_at(position, 1200 * (360 - 152) / 240)
    assert position.shape_id == "shape_93_trip"


@pytest.mark.spec("position_estimation.AC-11")
async def test_without_arrivals_of_the_line_and_direction(world: World) -> None:
    world.source.arrivals = (_sae("93", "Pass. Marítim", 4),)
    position = await world.execute(line="70", direction_id=1)
    assert position.status is PositionStatus.NO_ARRIVAL
    assert position.source is ArrivalSource.REALTIME
    assert position.arrival is None
    assert position.estimate is None
    assert position.shape_id == "shape_70"  # representative shape of the line and direction
    assert position.headsign == "Alboraia"


@pytest.mark.spec("position_estimation.AC-11")
async def test_an_arrival_without_a_paired_trip_has_no_vehicle(world: World) -> None:
    world.source.arrivals = (_sae("93", "Pass. Marítim", 60),)  # no trip within the tolerance
    position = await world.execute()
    assert position.status is PositionStatus.NO_VEHICLE
    assert position.arrival is not None
    assert position.arrival.vehicle is None
    assert position.arrival.minutes == 60
    assert position.estimate is None
    assert position.shape_id == "shape_93"


@pytest.mark.spec("position_estimation.AC-11")
async def test_a_paired_trip_without_timetable_or_shape_has_no_vehicle(world: World) -> None:
    world.source.arrivals = (_sae("93", "Pass. Marítim", 13),)  # paired with 93_123
    world.network.trips["93_123"] = []
    position = await world.execute()
    assert position.arrival is not None
    assert position.arrival.vehicle == VehicleView("93_123", DAY)
    assert (position.status, position.estimate, position.shape_id) == (
        PositionStatus.NO_VEHICLE,
        None,
        "shape_93",
    )
    world.network.trips["93_123"] = world.network.trips["93_122"]
    world.network.trip_shapes["93_123"] = "missing_shape"
    position = await world.execute()
    assert (position.status, position.estimate, position.shape_id) == (
        PositionStatus.NO_VEHICLE,
        None,
        "shape_93",
    )


@pytest.mark.spec("position_estimation.AC-12")
@pytest.mark.parametrize(
    ("stop_id", "token"), [("508", ""), ("508", "A" * 22), ("999", SIGNER.sign("999"))]
)
async def test_invalid_token_or_unknown_stop(world: World, stop_id: str, token: str) -> None:
    with pytest.raises(StopNotFoundError):
        await world.execute(stop_id=stop_id, token=token)
    assert world.source.calls == []


@pytest.mark.spec("position_estimation.AC-12")
async def test_invalid_token_wins_over_a_line_not_at_the_stop(world: World) -> None:
    with pytest.raises(StopNotFoundError):
        await world.execute(line="N4", token="A" * 22)


@pytest.mark.spec("position_estimation.AC-12")
@pytest.mark.parametrize(("line", "direction_id"), [("70", 0), ("93", 1), ("N4", 0)])
async def test_line_and_direction_not_at_the_stop(
    world: World, line: str, direction_id: int
) -> None:
    with pytest.raises(LineNotAtStopError) as raised:
        await world.execute(line=line, direction_id=direction_id)
    assert (raised.value.line, raised.value.direction_id) == (line, direction_id)
    assert line not in str(raised.value)


async def test_no_active_feed(world: World) -> None:
    world.network.feed = None
    with pytest.raises(NoActiveFeedError):
        await world.execute()
