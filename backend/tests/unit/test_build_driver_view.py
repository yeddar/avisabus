"""`BuildDriverView` with fakes (driver_demand T-01)."""

from dataclasses import dataclass, field
from datetime import date, timedelta

import pytest

from avisabus.application.build_driver_view import BuildDriverView
from avisabus.application.driver_sessions import GetDriverSession, TripRoute
from avisabus.domain.models.alert import AlertStatus, Need
from avisabus.domain.models.driver import DriverService, GpsState, UpcomingStop
from avisabus.domain.models.driver_view import DriverServiceView, DriverView, NeedCounts
from avisabus.domain.models.network import Departure, Line, TripStopTime
from avisabus.domain.models.occupancy import OccupancyThresholds, VehicleRef
from avisabus.domain.services.occupancy_simulation import service_day_start
from tests.support.alerts import FakeAlertRepository
from tests.support.demand import (
    MONDAY,
    NOW,
    SESSION,
    TRIP,
    FakeOccupancySensor,
    alert_at,
    occupancy,
)
from tests.support.drivers import InMemorySessions, session_of
from tests.support.fake_clock import FakeClock

SERVICE = DriverService("93", 0, TRIP, MONDAY)
DEPARTURE_S = 32000
STOPS = tuple((UpcomingStop(f"s{n}", f"Stop s{n}", n + 1, 0.0), float(n) * 500.0) for n in range(9))


class StubRoutes:
    def __init__(self, *known: str) -> None:
        self.known = known

    def of(self, trip_id: str) -> TripRoute | None:
        return TripRoute((), (), STOPS) if trip_id in self.known else None


@dataclass
class StubNetwork:
    """Only what `BuildDriverView` asks for the departure."""

    stop_times: list[TripStopTime] = field(
        # Out of order on purpose: the departure is the one of the lowest `stop_sequence`.
        default_factory=lambda: [
            TripStopTime("s1", 2, DEPARTURE_S + 60, DEPARTURE_S + 60, None),
            TripStopTime("s0", 1, DEPARTURE_S - 5, DEPARTURE_S, None),
        ]
    )
    line: Line | None = field(
        default_factory=lambda: Line("93", "Long name", "FE0000", "FFFFFF", frozenset({"r"}))
    )
    headsign: str | None = "Hospital Malva-rosa"
    departure_queries: list[tuple[str, int, date, int, int]] = field(default_factory=list)

    def trip_stop_times(self, trip_id: str) -> list[TripStopTime]:
        return self.stop_times if trip_id == TRIP else []

    def get_line(self, short_name: str) -> Line | None:
        return self.line if short_name == "93" else None

    def departures(
        self, line: str, direction_id: int, service_date: date, from_s: int, to_s: int
    ) -> list[Departure]:
        self.departure_queries.append((line, direction_id, service_date, from_s, to_s))
        if self.headsign is None:
            return []
        return [
            Departure("another-trip", service_date, from_s, "First", "Another headsign"),
            Departure(TRIP, service_date, from_s, "First", self.headsign),
        ]


@dataclass
class Harness:
    clock: FakeClock = field(default_factory=lambda: FakeClock(NOW))
    alerts: FakeAlertRepository = field(default_factory=FakeAlertRepository)
    network: StubNetwork = field(default_factory=StubNetwork)
    sensor: FakeOccupancySensor = field(default_factory=FakeOccupancySensor)
    sessions: InMemorySessions = field(default_factory=InMemorySessions)

    def build(self) -> BuildDriverView:
        state = GetDriverSession(StubRoutes(TRIP), self.clock, timedelta(seconds=30))
        return BuildDriverView(
            sessions=self.sessions,
            alerts=self.alerts,
            network=self.network,
            state=state,
            occupancy=self.sensor,
            thresholds=OccupancyThresholds(),
            clock=self.clock,
        )

    def add_alert(self, *args: object, **kwargs: object) -> None:
        alert = alert_at(*args, **kwargs)  # type: ignore[arg-type]
        self.alerts.alerts[alert.alert_id] = alert


# 200 m along the shape: stops s1 (500 m) to s5 (2500 m) are ahead.
RUNNING = {"service": SERVICE, "progress_m": 200.0, "last_position_at": NOW}


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.mark.spec("driver_demand.AC-05")
async def test_the_view_describes_the_departure_and_the_state(harness: Harness) -> None:
    view = await harness.build().execute(session_of(1, **RUNNING))

    assert view.generated_at == NOW
    assert view.service == DriverServiceView(
        line="93",
        direction_id=0,
        headsign="Hospital Malva-rosa",
        trip_id=TRIP,
        service_date=MONDAY,
        departure_at=service_day_start(MONDAY) + timedelta(seconds=DEPARTURE_S),
        color="FE0000",
        text_color="FFFFFF",
    )
    assert (view.gps, view.off_route, view.finished) == (GpsState.OK, False, False)
    assert harness.network.departure_queries == [("93", 0, MONDAY, DEPARTURE_S, DEPARTURE_S)]


@pytest.mark.spec("driver_demand.AC-05")
async def test_the_view_shows_up_to_five_stops_with_their_demand(harness: Harness) -> None:
    harness.add_alert(1, "s1", 2, (Need.RAMP, Need.SEAT))
    harness.add_alert(2, "s1", 2, (Need.VISUAL,))
    harness.add_alert(3, "s3", 4, (Need.EXTRA_TIME,))

    view = await harness.build().execute(session_of(1, **RUNNING))

    assert [stop.stop_id for stop in view.stops] == ["s1", "s2", "s3", "s4", "s5"]
    assert [stop.waiting for stop in view.stops] == [2, 0, 1, 0, 0]
    assert view.stops[0].distance_m == 300.0
    assert view.stops[0].needs == NeedCounts(RAMP=1, SEAT=1, VISUAL=1)
    assert view.stops[0].alert_ids == ("alert-1", "alert-2")
    assert view.total_waiting == 3


@pytest.mark.spec("driver_demand.AC-05")
async def test_the_total_only_adds_the_stops_shown(harness: Harness) -> None:
    harness.add_alert(1, "s1", 2)
    harness.add_alert(2, "s8", 9)  # past the five stops shown

    view = await harness.build().execute(session_of(1, **RUNNING))

    assert view.total_waiting == 1


@pytest.mark.spec("driver_demand.AC-05")
async def test_only_requests_delivered_to_this_shift_count(harness: Harness) -> None:
    harness.add_alert(1, "s1", 2)
    harness.add_alert(2, "s1", 2, delivered_to="session-2")
    harness.add_alert(3, "s1", 2, status=AlertStatus.PENDING_DRIVER, delivered_to=None)

    view = await harness.build().execute(session_of(1, **RUNNING))

    assert view.stops[0].alert_ids == ("alert-1",)


@pytest.mark.spec("driver_demand.AC-05")
async def test_the_view_has_no_data_of_the_device(harness: Harness) -> None:
    harness.add_alert(1, "s1", 2, (Need.RAMP,))

    view = await harness.build().execute(session_of(1, **RUNNING))

    assert "device" not in repr(view)


@pytest.mark.spec("driver_demand.AC-05")
async def test_the_gps_state_comes_from_the_session(harness: Harness) -> None:
    build = harness.build()
    stale = NOW - timedelta(seconds=31)

    waiting = await build.execute(session_of(1, service=SERVICE))
    old = await build.execute(session_of(1, service=SERVICE, last_position_at=stale))

    assert waiting.gps is GpsState.WAITING
    assert old.gps is GpsState.STALE


@pytest.mark.spec("driver_demand.AC-05")
async def test_a_finished_trip_shows_no_stops(harness: Harness) -> None:
    view = await harness.build().execute(
        session_of(1, service=SERVICE, progress_m=4000.0, last_position_at=NOW, off_route=True)
    )

    assert (view.finished, view.off_route) == (True, True)
    assert view.stops == ()
    assert view.total_waiting == 0


@pytest.mark.spec("driver_demand.AC-06")
async def test_free_places_come_from_the_sensor_for_the_trip_of_the_shift(
    harness: Harness,
) -> None:
    harness.sensor.reading = occupancy(free_places=30, free_seats=4)

    view = await harness.build().execute(session_of(1, **RUNNING))

    assert (view.free_places, view.free_seats) == (30, 4)
    assert harness.sensor.queries == [(VehicleRef(TRIP, MONDAY), NOW)]
    assert (view.capacity_alert, view.seat_alert) == (False, False)


@pytest.mark.spec("driver_demand.AC-06")
async def test_more_people_waiting_than_free_places_raises_the_alerts(harness: Harness) -> None:
    harness.sensor.reading = occupancy(free_places=1, free_seats=0)
    harness.add_alert(1, "s1", 2, (Need.SEAT,))
    harness.add_alert(2, "s2", 3)

    view = await harness.build().execute(session_of(1, **RUNNING))

    assert (view.capacity_alert, view.seat_alert) == (True, True)


@pytest.mark.spec("driver_demand.AC-06")
async def test_without_occupancy_data_there_are_no_alerts(harness: Harness) -> None:
    harness.add_alert(1, "s1", 2, (Need.SEAT,))

    view = await harness.build().execute(session_of(1, **RUNNING))

    assert (view.free_places, view.free_seats) == (None, None)
    assert (view.capacity_alert, view.seat_alert) == (False, False)


def _assert_no_service(view: DriverView) -> None:
    assert view.service is None
    assert view.stops == ()
    assert view.total_waiting == 0
    assert (view.free_places, view.free_seats) == (None, None)
    assert (view.capacity_alert, view.seat_alert) == (False, False)


@pytest.mark.spec("driver_demand.AC-07")
async def test_without_a_departure_there_are_no_stops_nor_alerts(harness: Harness) -> None:
    harness.sensor.reading = occupancy(free_places=0, free_seats=0)
    harness.add_alert(1, "s1", 2)

    view = await harness.build().execute(session_of(1))

    _assert_no_service(view)
    assert view.gps is GpsState.WAITING
    assert harness.sensor.queries == []


@pytest.mark.spec("driver_demand.AC-07")
@pytest.mark.parametrize("missing", ["stop_times", "line", "departure"])
async def test_a_departure_gone_from_the_active_network_shows_as_no_departure(
    harness: Harness, missing: str
) -> None:
    if missing == "stop_times":
        harness.network.stop_times = []
    elif missing == "line":
        harness.network.line = None
    else:
        harness.network.headsign = None

    _assert_no_service(await harness.build().execute(session_of(1, **RUNNING)))


async def test_it_finds_an_open_shift_by_id(harness: Harness) -> None:
    harness.sessions.add(session_of(1, **RUNNING))
    harness.sessions.add(session_of(2))
    build = harness.build()

    found = await build.for_session_id(SESSION)

    assert found is not None
    assert found.service is not None
    assert await build.for_session_id("gone") is None
    assert build.open_session_ids() == ["session-1", "session-2"]
