"""Departure, position, state and end of a shift with fakes (driver_session T-04)."""

import math
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from avisabus.application.close_driver_session import CloseDriverSession
from avisabus.application.driver_sessions import (
    AuthenticateDriverSession,
    EndDriverSession,
    GetDriverSession,
    SelectDriverService,
    SelectDriverServiceCommand,
    TripRoutes,
    UpdateDriverPosition,
    UpdateDriverPositionCommand,
)
from avisabus.domain.errors import (
    DepartureTakenError,
    InvalidDepartureError,
    InvalidPositionError,
    InvalidSessionError,
    NoActiveFeedError,
)
from avisabus.domain.models.driver import (
    DriverPosition,
    DriverService,
    GpsState,
    SessionCloseReason,
)
from avisabus.domain.models.network import (
    Departure,
    FeedVersion,
    ShapePoint,
    Stop,
    TripStopTime,
)
from avisabus.domain.services.geometry import EARTH_RADIUS_M, cumulative_distances
from tests.support.drivers import InMemorySessions, RecordingListener, RecordingLogger, session_of
from tests.support.fake_clock import FakeClock

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)  # 09:00 in Madrid: second 32400 of Monday
MONDAY = date(2026, 11, 9)
SERVICE = DriverService("93", 0, "trip-1", MONDAY)
FEED = FeedVersion(1, "v", NOW, date(2026, 11, 1), date(2026, 12, 1), {})
ORIGIN_LAT = 39.47
ORIGIN_LON = -0.37
TOLERANCE_M = 0.5


def lat_lon(east_m: float, north_m: float = 0.0) -> tuple[float, float]:
    lat = ORIGIN_LAT + math.degrees(north_m / EARTH_RADIUS_M)
    lon = ORIGIN_LON + math.degrees(east_m / (EARTH_RADIUS_M * math.cos(math.radians(ORIGIN_LAT))))
    return lat, lon


def _shape(*east: float) -> list[ShapePoint]:
    points = []
    for n, x in enumerate(east, start=1):
        lat, lon = lat_lon(x)
        points.append(ShapePoint(lat, lon, n, x))
    return points


# A straight 5 km shape with stops every kilometre.
SHAPE = _shape(0, 1000, 2000, 3000, 4000, 5000)
STOP_TIMES = [TripStopTime(f"s{n}", n, 0, 0, float(n * 1000)) for n in range(6)]


class FakeNetwork:
    def __init__(
        self,
        stop_times: list[TripStopTime] | None = None,
        shape: list[ShapePoint] | None = None,
        departures: list[Departure] | None = None,
        feed: FeedVersion | None = FEED,
    ) -> None:
        self.stop_times = STOP_TIMES if stop_times is None else stop_times
        self.shape = SHAPE if shape is None else shape
        self._departures = departures
        self.feed = feed
        self.shape_loads = 0

    def active_feed(self) -> FeedVersion | None:
        return self.feed

    def departures(
        self, _line: str, _direction: int, service_date: date, from_s: int, to_s: int
    ) -> list[Departure]:
        if self._departures is None:
            rows = [Departure("trip-1", MONDAY, 32400, "First", "Head")]
        else:
            rows = self._departures
        return [
            d for d in rows if d.service_date == service_date and from_s <= d.departure_s <= to_s
        ]

    def trip_shape_id(self, trip_id: str) -> str | None:
        return "shape-1" if trip_id == "trip-1" else None

    def trip_stop_times(self, trip_id: str) -> list[TripStopTime]:
        return self.stop_times if trip_id == "trip-1" else []

    def shape_points(self, _shape_id: str) -> list[ShapePoint]:
        self.shape_loads += 1
        return self.shape

    def get_stop(self, stop_id: str) -> Stop | None:
        lat, lon = lat_lon(int(stop_id[1:]) * 1000)
        return Stop(stop_id, f"Stop {stop_id}", lat, lon)


class Harness:
    def __init__(self, *sessions, network: FakeNetwork | None = None) -> None:  # noqa: ANN002
        self.clock = FakeClock(NOW)
        self.network = network or FakeNetwork()
        self.sessions = InMemorySessions(*sessions)
        self.listener = RecordingListener()
        self.logger = RecordingLogger()
        self.routes = TripRoutes(self.network)
        self.close = CloseDriverSession(self.sessions, self.listener, self.clock, self.logger)
        self.get = GetDriverSession(self.routes, self.clock, timedelta(seconds=30))
        self.select = SelectDriverService(
            self.network, self.sessions, self.listener, self.get, self.clock, self.logger
        )
        self.update = UpdateDriverPosition(self.sessions, self.routes, self.listener, self.clock)
        self.end = EndDriverSession(self.close)

    def stored(self, number: int = 1):  # noqa: ANN201
        return self.sessions.rows[f"session-{number}"]

    async def send(
        self,
        east: float,
        north: float = 0.0,
        recorded_at: datetime | None = None,
        session=None,  # noqa: ANN001
    ) -> None:
        lat, lon = lat_lon(east, north)
        await self.update.execute(
            UpdateDriverPositionCommand(
                session=session or self.stored(),
                lat=lat,
                lon=lon,
                accuracy_m=5.0,
                recorded_at=recorded_at or self.clock.now(),
            )
        )


def _on_service(**values) -> Harness:  # noqa: ANN003
    """A shift on its departure; a given progress was fixed a minute ago (window of 1250 m)."""
    if values.get("progress_m") is not None:
        values.setdefault("progress_recorded_at", NOW - timedelta(seconds=60))
    return Harness(session_of(1, SERVICE, **values))


# --- AC-07: departure ---------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-07")
async def test_selecting_a_departure_stores_it() -> None:
    harness = Harness(session_of(1))
    state = await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    assert harness.stored().service == SERVICE
    assert state.service == SERVICE
    assert state.session_id == "session-1"


@pytest.mark.spec("driver_session.AC-07")
async def test_selecting_a_departure_resets_the_progress_and_notifies() -> None:
    previous = DriverService("93", 0, "trip-0", MONDAY)
    harness = Harness(session_of(1, previous, progress_m=900.0, off_route=True))
    await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    assert harness.stored().progress_m is None
    assert harness.stored().off_route is False
    assert harness.listener.calls == [("service_selected", "session-1", previous)]


@pytest.mark.spec("driver_session.AC-07")
async def test_selecting_keeps_the_last_position() -> None:
    position = DriverPosition(39.0, -0.3, 5.0, NOW)
    harness = Harness(session_of(1, position=position, last_position_at=NOW))
    await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    assert harness.stored().position == position
    assert harness.stored().last_position_at == NOW


@pytest.mark.spec("driver_session.AC-07")
async def test_a_first_selection_has_no_previous_service() -> None:
    harness = Harness(session_of(1))
    await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    assert harness.listener.calls == [("service_selected", "session-1", None)]


@pytest.mark.spec("driver_session.AC-07")
@pytest.mark.parametrize(
    "service",
    [
        DriverService("93", 0, "other-trip", MONDAY),
        DriverService("93", 0, "trip-1", date(2026, 11, 7)),
        DriverService("93", 0, "trip-1", date(2026, 11, 10)),
    ],
)
async def test_a_departure_that_would_not_be_offered_is_invalid(service: DriverService) -> None:
    harness = Harness(session_of(1))
    with pytest.raises(InvalidDepartureError):
        await harness.select.execute(SelectDriverServiceCommand(harness.stored(), service))
    assert harness.stored().service is None
    assert harness.listener.calls == []


@pytest.mark.spec("driver_session.AC-07")
async def test_a_departure_outside_the_window_is_invalid() -> None:
    harness = Harness(session_of(1))
    harness.clock.advance(timedelta(minutes=31))
    with pytest.raises(InvalidDepartureError):
        await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))


@pytest.mark.spec("driver_session.AC-07")
async def test_a_departure_held_by_another_shift_is_taken() -> None:
    harness = Harness(session_of(1), session_of(2, SERVICE))
    with pytest.raises(DepartureTakenError):
        await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    assert harness.stored().service is None
    assert harness.listener.calls == []


@pytest.mark.spec("driver_session.AC-07")
async def test_the_driver_can_select_again_the_departure_it_holds() -> None:
    harness = _on_service(progress_m=500.0)
    await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    assert harness.stored().progress_m is None


@pytest.mark.spec("driver_session.AC-07")
async def test_validity_comes_first_when_a_departure_is_invalid_and_held() -> None:
    held_but_invalid = DriverService("93", 0, "trip-9", MONDAY)
    harness = Harness(session_of(1), session_of(2, held_but_invalid))
    with pytest.raises(InvalidDepartureError):
        await harness.select.execute(SelectDriverServiceCommand(harness.stored(), held_but_invalid))


@pytest.mark.spec("driver_session.AC-07")
async def test_selecting_without_an_active_feed_is_unavailable() -> None:
    harness = Harness(session_of(1), network=FakeNetwork(feed=None))
    with pytest.raises(NoActiveFeedError):
        await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))


@pytest.mark.spec("driver_session.AC-15")
async def test_service_selected_is_logged() -> None:
    harness = Harness(session_of(1))
    await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    assert harness.logger.named("driver.service_selected") == [
        {"session_id": "session-1", "line": "93", "direction_id": 0, "trip_id": "trip-1"}
    ]


# --- AC-08: position ----------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-08")
async def test_position_is_stored_with_the_server_instant() -> None:
    harness = Harness(session_of(1))
    recorded = NOW - timedelta(seconds=3)
    await harness.send(100, recorded_at=recorded)
    stored = harness.stored()
    assert stored.position is not None
    assert stored.position.recorded_at == recorded
    assert stored.position.accuracy_m == 5.0
    assert stored.last_position_at == NOW
    assert harness.listener.calls == [("position_updated", "session-1")]


@pytest.mark.spec("driver_session.AC-08")
async def test_only_the_last_position_is_kept() -> None:
    harness = Harness(session_of(1))
    await harness.send(100, recorded_at=NOW - timedelta(seconds=10))
    await harness.send(200, recorded_at=NOW - timedelta(seconds=5))
    assert harness.stored().position is not None
    assert harness.stored().position.lon == pytest.approx(lat_lon(200)[1])


@pytest.mark.spec("driver_session.AC-08")
async def test_an_older_position_is_discarded() -> None:
    harness = _on_service(progress_m=2000.0)
    await harness.send(2000, recorded_at=NOW)
    before = harness.stored()
    harness.clock.advance(timedelta(seconds=5))
    await harness.send(9000, recorded_at=NOW - timedelta(seconds=1))
    assert harness.stored() == before
    assert harness.listener.calls == [("position_updated", "session-1")]


@pytest.mark.spec("driver_session.AC-08")
async def test_a_position_with_the_same_time_is_accepted() -> None:
    harness = Harness(session_of(1))
    await harness.send(100, recorded_at=NOW)
    await harness.send(200, recorded_at=NOW)
    assert harness.stored().position is not None
    assert harness.stored().position.lon == pytest.approx(lat_lon(200)[1])


@pytest.mark.spec("driver_session.AC-08")
async def test_a_position_more_than_30_s_ahead_is_invalid() -> None:
    harness = Harness(session_of(1))
    with pytest.raises(InvalidPositionError):
        await harness.send(100, recorded_at=NOW + timedelta(seconds=31))
    assert harness.stored().position is None
    assert harness.listener.calls == []


@pytest.mark.spec("driver_session.AC-08")
@pytest.mark.parametrize(
    "recorded_at",
    [
        datetime(9999, 12, 31, 23, 59, 59, tzinfo=timezone(timedelta(hours=-14))),
        datetime(1, 1, 1, 0, 0, tzinfo=timezone(timedelta(hours=14))),
    ],
)
async def test_a_date_outside_the_calendar_in_utc_is_invalid(recorded_at: datetime) -> None:
    harness = Harness(session_of(1))
    with pytest.raises(InvalidPositionError):
        await harness.send(100, recorded_at=recorded_at)
    assert harness.stored().position is None
    assert harness.listener.calls == []


@pytest.mark.spec("driver_session.AC-08")
async def test_a_position_exactly_30_s_ahead_is_accepted() -> None:
    harness = Harness(session_of(1))
    await harness.send(100, recorded_at=NOW + timedelta(seconds=30))
    assert harness.stored().position is not None


@pytest.mark.spec("driver_session.AC-08")
async def test_a_position_without_a_service_only_keeps_the_position() -> None:
    harness = Harness(session_of(1))
    await harness.send(1000)
    assert harness.stored().progress_m is None
    assert harness.stored().off_route is False


# --- AC-09: progress ----------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-09")
async def test_the_first_position_sets_the_progress_anywhere_on_the_shape() -> None:
    harness = _on_service()
    await harness.send(4200)
    assert harness.stored().progress_m == pytest.approx(4200, abs=TOLERANCE_M)
    assert harness.stored().off_route is False


@pytest.mark.spec("driver_session.AC-09")
async def test_the_progress_advances_with_the_position() -> None:
    harness = _on_service(progress_m=1000.0)
    await harness.send(1500)
    assert harness.stored().progress_m == pytest.approx(1500, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
async def test_the_progress_does_not_go_back() -> None:
    harness = _on_service(progress_m=1000.0)
    await harness.send(950)
    assert harness.stored().progress_m == 1000.0


@pytest.mark.spec("driver_session.AC-09")
async def test_the_search_is_limited_by_the_time_since_the_last_position_on_route() -> None:
    harness = _on_service(progress_m=1000.0, progress_recorded_at=NOW - timedelta(seconds=10))
    await harness.send(1500)  # 20 m/s × 10 s + 50 m reach 1250 m: 250 m from the window
    assert harness.stored().off_route is True
    assert harness.stored().progress_m == 1000.0


@pytest.mark.spec("driver_session.AC-09")
async def test_the_elapsed_time_uses_the_recorded_at_of_the_positions() -> None:
    harness = _on_service(progress_m=1000.0, progress_recorded_at=NOW - timedelta(seconds=10))
    await harness.send(1400, recorded_at=NOW + timedelta(seconds=10))  # 20 s of GPS time
    assert harness.stored().progress_m == pytest.approx(1400, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
async def test_a_position_on_route_moves_the_mark_of_the_elapsed_time() -> None:
    harness = _on_service(progress_m=1000.0)
    await harness.send(1500)
    assert harness.stored().progress_recorded_at == NOW


@pytest.mark.spec("driver_session.AC-09")
async def test_a_position_on_route_that_does_not_advance_also_moves_the_mark() -> None:
    harness = _on_service(progress_m=1000.0)
    await harness.send(950)
    assert harness.stored().progress_m == 1000.0
    assert harness.stored().progress_recorded_at == NOW


@pytest.mark.spec("driver_session.AC-09")
async def test_off_route_keeps_the_mark_so_the_search_goes_on_growing() -> None:
    mark = NOW - timedelta(seconds=10)
    harness = _on_service(progress_m=1000.0, progress_recorded_at=mark)
    await harness.send(1650)  # 10 s since the mark: reaches 1250
    assert harness.stored().off_route is True
    assert harness.stored().progress_recorded_at == mark

    harness.clock.advance(timedelta(seconds=10))
    await harness.send(1650, recorded_at=harness.clock.now())  # 20 s: reaches 1450, 200 m away

    assert harness.stored().off_route is True
    harness.clock.advance(timedelta(seconds=10))
    await harness.send(1650, recorded_at=harness.clock.now())  # 30 s: reaches 1650

    assert harness.stored().off_route is False
    assert harness.stored().progress_m == pytest.approx(1650, abs=TOLERANCE_M)
    assert harness.stored().progress_recorded_at == harness.clock.now()


@pytest.mark.spec("driver_session.AC-09")
async def test_a_gps_gap_of_five_minutes_recovers_the_progress() -> None:
    harness = _on_service(progress_m=1000.0, progress_recorded_at=NOW)
    harness.clock.advance(timedelta(minutes=5))
    await harness.send(4800, recorded_at=harness.clock.now())
    assert harness.stored().off_route is False
    assert harness.stored().progress_m == pytest.approx(4800, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
async def test_the_first_position_on_route_sets_the_mark() -> None:
    harness = _on_service()
    await harness.send(1200, recorded_at=NOW - timedelta(seconds=2))
    assert harness.stored().progress_recorded_at == NOW - timedelta(seconds=2)


@pytest.mark.spec("driver_session.AC-09")
async def test_a_first_position_off_route_leaves_no_mark() -> None:
    harness = _on_service()
    await harness.send(1000, north=500)
    assert harness.stored().progress_m is None
    assert harness.stored().progress_recorded_at is None


@pytest.mark.spec("driver_session.AC-09")
async def test_a_position_without_service_leaves_no_mark() -> None:
    harness = Harness(session_of(1))
    await harness.send(1000)
    assert harness.stored().progress_recorded_at is None


@pytest.mark.spec("driver_session.AC-09")
async def test_a_new_departure_clears_the_mark() -> None:
    previous = DriverService("93", 0, "trip-0", MONDAY)
    harness = Harness(
        session_of(1, previous, progress_m=900.0, progress_recorded_at=NOW - timedelta(seconds=9))
    )
    await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    assert harness.stored().progress_m is None
    assert harness.stored().progress_recorded_at is None


@pytest.mark.spec("driver_session.AC-09")
async def test_after_a_new_departure_the_first_position_searches_the_whole_shape() -> None:
    harness = _on_service(progress_m=100.0)
    await harness.select.execute(SelectDriverServiceCommand(harness.stored(), SERVICE))
    await harness.send(4200)
    assert harness.stored().progress_m == pytest.approx(4200, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
async def test_off_route_beyond_150_m_keeps_the_progress() -> None:
    harness = _on_service(progress_m=1000.0)
    await harness.send(1500, north=151)
    assert harness.stored().off_route is True
    assert harness.stored().progress_m == 1000.0


@pytest.mark.spec("driver_session.AC-09")
async def test_at_150_m_from_the_shape_it_is_still_on_route() -> None:
    harness = _on_service(progress_m=1000.0)
    await harness.send(1500, north=149.5)
    assert harness.stored().off_route is False
    assert harness.stored().progress_m == pytest.approx(1500, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
async def test_coming_back_to_the_route_clears_off_route() -> None:
    harness = _on_service(progress_m=1000.0, off_route=True)
    await harness.send(1200)
    assert harness.stored().off_route is False


@pytest.mark.spec("driver_session.AC-09")
async def test_the_first_position_off_route_leaves_no_progress() -> None:
    harness = _on_service()
    await harness.send(1000, north=500)
    assert harness.stored().off_route is True
    assert harness.stored().progress_m is None


@pytest.mark.spec("driver_session.AC-09")
async def test_stop_distances_come_from_the_shape_if_the_feed_lacks_them() -> None:
    stop_times = [replace(st, shape_dist_traveled=None) for st in STOP_TIMES]
    harness = Harness(
        session_of(1, SERVICE, progress_m=1500.0), network=FakeNetwork(stop_times=stop_times)
    )
    state = await harness.get.execute(harness.stored())
    assert [stop.stop_id for stop in state.progress.upcoming[:2]] == ["s2", "s3"]
    assert state.progress.upcoming[0].distance_m == pytest.approx(500, abs=TOLERANCE_M)


# A feed like EMT's: its `shape_dist_traveled` are not metres (each kilometre counts as 3000).
INFLATED_SHAPE = [replace(p, dist_traveled=(p.dist_traveled or 0.0) * 3) for p in SHAPE]
INFLATED_STOPS = [
    replace(st, shape_dist_traveled=(st.shape_dist_traveled or 0.0) * 3) for st in STOP_TIMES
]


def _inflated(**values) -> FakeNetwork:  # noqa: ANN003
    return FakeNetwork(**{"stop_times": INFLATED_STOPS, "shape": INFLATED_SHAPE, **values})


@pytest.mark.spec("driver_session.AC-09")
def test_the_route_measures_the_shape_in_real_metres() -> None:
    route = TripRoutes(_inflated()).of("trip-1")
    assert route is not None
    assert route.distances == pytest.approx(cumulative_distances(SHAPE))
    assert route.distances[-1] == pytest.approx(5000, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-10")
def test_stops_of_the_feed_are_converted_to_real_metres() -> None:
    route = TripRoutes(_inflated()).of("trip-1")
    assert route is not None
    assert [along for _, along in route.stops] == pytest.approx(
        [1000.0 * n for n in range(6)], abs=TOLERANCE_M
    )


@pytest.mark.spec("driver_session.AC-10")
def test_stops_never_go_back_along_the_trip() -> None:
    out_of_order = [
        replace(st, shape_dist_traveled=d)
        for st, d in zip(STOP_TIMES, [0, 3000, 2400, 9000, 12000, 15000], strict=True)
    ]
    route = TripRoutes(FakeNetwork(stop_times=out_of_order, shape=INFLATED_SHAPE)).of("trip-1")
    assert route is not None
    alongs = [along for _, along in route.stops]
    assert alongs == sorted(alongs)
    assert alongs[2] == pytest.approx(1000, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-10")
def test_stops_are_projected_if_the_shape_lacks_the_feed_distance() -> None:
    shape = [replace(p, dist_traveled=None) for p in SHAPE]
    route = TripRoutes(FakeNetwork(shape=shape)).of("trip-1")
    assert route is not None
    assert [along for _, along in route.stops] == pytest.approx(
        [1000.0 * n for n in range(6)], abs=TOLERANCE_M
    )


@pytest.mark.spec("driver_session.AC-09")
async def test_the_progress_is_in_real_metres_with_a_feed_not_in_metres() -> None:
    harness = Harness(session_of(1, SERVICE), network=_inflated())
    await harness.send(1500)
    assert harness.stored().progress_m == pytest.approx(1500, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
async def test_the_window_is_in_real_metres_with_a_feed_not_in_metres() -> None:
    mark = NOW - timedelta(seconds=10)
    harness = Harness(
        session_of(1, SERVICE, progress_m=1000.0, progress_recorded_at=mark),
        network=_inflated(),
    )
    await harness.send(1200)  # 10 s reach 1250 real metres
    assert harness.stored().off_route is False
    assert harness.stored().progress_m == pytest.approx(1200, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-10")
async def test_upcoming_distances_are_real_metres() -> None:
    harness = Harness(session_of(1, SERVICE, progress_m=1500.0), network=_inflated())
    state = await harness.get.execute(harness.stored())
    assert state.progress.upcoming[0].stop_id == "s2"
    assert state.progress.upcoming[0].distance_m == pytest.approx(500, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
async def test_a_trip_gone_from_the_network_keeps_the_session_working() -> None:
    gone = DriverService("93", 0, "trip-gone", MONDAY)
    harness = Harness(session_of(1, gone, progress_m=100.0))
    await harness.send(1500)
    assert harness.stored().progress_m == 100.0
    assert harness.stored().position is not None
    state = await harness.get.execute(harness.stored())
    assert state.progress.upcoming == ()


@pytest.mark.spec("driver_session.AC-09")
async def test_the_route_of_a_trip_is_cached() -> None:
    harness = _on_service()
    await harness.send(100)
    await harness.send(200)
    await harness.get.execute(harness.stored())
    assert harness.network.shape_loads == 1


@pytest.mark.spec("driver_session.AC-09")
async def test_the_cache_is_dropped_with_a_new_feed_version() -> None:
    harness = _on_service()
    await harness.send(100)
    harness.network.feed = replace(FEED, version_id=2)
    await harness.send(200)
    assert harness.network.shape_loads == 2


@pytest.mark.spec("driver_session.AC-09")
async def test_two_stop_patterns_of_a_shape_are_cached_apart() -> None:
    network = FakeNetwork()
    routes = TripRoutes(network)
    full = routes.of("trip-1")
    assert full is not None
    network.stop_times = STOP_TIMES[:3]
    short = routes.of("trip-1")
    assert short is not None
    assert len(short.stops) == 3
    assert len(full.stops) == 6


@pytest.mark.spec("driver_session.AC-09")
def test_no_route_without_an_active_feed_or_a_shape_or_stops() -> None:
    assert TripRoutes(FakeNetwork(feed=None)).of("trip-1") is None
    assert TripRoutes(FakeNetwork()).of("other") is None
    assert TripRoutes(FakeNetwork(stop_times=[])).of("trip-1") is None
    assert TripRoutes(FakeNetwork(shape=[])).of("trip-1") is None


@pytest.mark.spec("driver_session.AC-09")
def test_no_route_when_a_stop_is_missing_from_the_network() -> None:
    class MissingStops(FakeNetwork):
        def get_stop(self, stop_id: str) -> Stop | None:
            return None

    assert TripRoutes(MissingStops()).of("trip-1") is None


# --- AC-10, AC-11: state ------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-10")
async def test_state_lists_the_next_stops_from_the_progress() -> None:
    harness = _on_service(progress_m=1500.0)
    state = await harness.get.execute(harness.stored())
    assert [
        (stop.stop_id, stop.stop_sequence, round(stop.distance_m))
        for stop in state.progress.upcoming
    ] == [("s2", 2, 500), ("s3", 3, 1500), ("s4", 4, 2500), ("s5", 5, 3500)]
    assert state.progress.upcoming[0].name == "Stop s2"
    assert state.progress.finished is False


@pytest.mark.spec("driver_session.AC-10")
async def test_state_is_finished_at_the_last_stop() -> None:
    harness = _on_service(progress_m=4990.0)
    state = await harness.get.execute(harness.stored())
    assert state.progress.finished is True
    assert state.progress.upcoming == ()


@pytest.mark.spec("driver_session.AC-10")
async def test_a_position_reaching_the_last_stop_finishes_the_trip() -> None:
    harness = _on_service(progress_m=4900.0)
    await harness.send(4985)
    state = await harness.get.execute(harness.stored())
    assert state.progress.finished is True


@pytest.mark.spec("driver_session.AC-11")
async def test_state_without_service_nor_position() -> None:
    harness = Harness(session_of(1))
    state = await harness.get.execute(harness.stored())
    assert state.service is None
    assert state.progress.gps is GpsState.WAITING
    assert state.progress.off_route is False
    assert state.progress.finished is False
    assert state.progress.upcoming == ()


@pytest.mark.spec("driver_session.AC-11")
async def test_without_progress_there_are_no_upcoming_stops() -> None:
    harness = _on_service()
    state = await harness.get.execute(harness.stored())
    assert state.service == SERVICE
    assert state.progress.upcoming == ()
    assert state.progress.finished is False


@pytest.mark.spec("driver_session.AC-11")
async def test_gps_is_ok_with_a_recent_position() -> None:
    harness = Harness(session_of(1))
    await harness.send(100)
    harness.clock.advance(timedelta(seconds=30))
    assert (await harness.get.execute(harness.stored())).progress.gps is GpsState.OK


@pytest.mark.spec("driver_session.AC-11")
async def test_gps_is_stale_after_30_seconds() -> None:
    harness = Harness(session_of(1))
    await harness.send(100)
    harness.clock.advance(timedelta(seconds=30, milliseconds=1))
    assert (await harness.get.execute(harness.stored())).progress.gps is GpsState.STALE


@pytest.mark.spec("driver_session.AC-11")
async def test_off_route_is_reported() -> None:
    harness = _on_service(progress_m=100.0, off_route=True)
    assert (await harness.get.execute(harness.stored())).progress.off_route is True


# --- AC-04: token -------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-04")
async def test_authenticate_finds_the_session_by_the_hash_of_its_token() -> None:
    class Hasher:
        def hash(self, token: str) -> str:
            return f"h({token})"

    session = session_of(1, token_hash="h(secret)")  # noqa: S106
    use_case = AuthenticateDriverSession(InMemorySessions(session), Hasher())
    assert await use_case.execute("secret") == session
    with pytest.raises(InvalidSessionError):
        await use_case.execute("other")


# --- AC-12: end ---------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-12")
async def test_ending_deletes_the_session_and_notifies() -> None:
    harness = Harness(session_of(1, position=DriverPosition(1.0, 2.0, 3.0, NOW)))
    await harness.end.execute(harness.stored())
    assert harness.sessions.list_all() == []
    assert harness.listener.calls == [("session_closed", "session-1", SessionCloseReason.ENDED)]


@pytest.mark.spec("driver_session.AC-12")
async def test_closing_twice_is_harmless() -> None:
    harness = Harness(session_of(1))
    await harness.close.execute("session-1", SessionCloseReason.ENDED)
    await harness.close.execute("session-1", SessionCloseReason.IDLE)
    assert len(harness.listener.calls) == 1
    assert len(harness.logger.named("driver.session_closed")) == 1


@pytest.mark.spec("driver_session.AC-12")
async def test_closing_an_unknown_session_does_nothing() -> None:
    harness = Harness()
    await harness.close.execute("session-9", SessionCloseReason.IDLE)
    assert harness.listener.calls == []


@pytest.mark.spec("driver_session.AC-15")
async def test_session_closed_is_logged_with_reason_and_duration() -> None:
    harness = Harness(session_of(1, started_at=NOW - timedelta(minutes=90)))
    await harness.close.execute("session-1", SessionCloseReason.REVOKED)
    assert harness.logger.named("driver.session_closed") == [
        {"session_id": "session-1", "reason": "REVOKED", "duration_s": 5400}
    ]


@pytest.mark.spec("driver_session.AC-15")
async def test_coordinates_never_reach_the_log() -> None:
    harness = _on_service()
    await harness.send(1234)
    await harness.close.execute("session-1", SessionCloseReason.ENDED)
    lat, lon = lat_lon(1234)
    logged = repr(harness.logger.events)
    assert str(round(lat, 3)) not in logged
    assert str(round(lon, 3)) not in logged
