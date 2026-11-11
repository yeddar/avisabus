"""Publication of the driver views, grouped per shift (driver_demand T-03)."""

import asyncio
from dataclasses import dataclass, field, replace
from datetime import timedelta
from typing import Any

import pytest

from avisabus.adapters.outbound.drivers.demand_listener import (
    DemandSessionListener,
    DemandViewNotifier,
)
from avisabus.application.demand_views import (
    DRIVER_VIEW,
    SESSION_CLOSED,
    DemandViews,
    driver_channel,
    driver_view_payload,
)
from avisabus.application.driver_sessions import TripRoute
from avisabus.background.alert_tasks import stop_tasks
from avisabus.background.driver_tasks import (
    DEMAND_VIEW_REFRESHER,
    VIEW_REFRESH_INTERVAL,
    start_demand_tasks,
)
from avisabus.domain.models.driver import (
    DriverPosition,
    DriverService,
    DriverSession,
    GpsState,
    SessionCloseReason,
    UpcomingStop,
)
from avisabus.domain.models.driver_view import (
    DriverServiceView,
    DriverView,
    NeedCounts,
    StopDemand,
)
from tests.support.demand import MONDAY, NOW, SESSION, TRIP, ChannelPublisher
from tests.support.drivers import RecordingLogger, session_of
from tests.support.fake_clock import FakeClock
from tests.support.ws import FakeSleep

CHANNEL = driver_channel(SESSION)
SERVICE = DriverService("93", 0, TRIP, MONDAY)
TURNS = 50


def _view(**values: Any) -> DriverView:
    fields: dict[str, Any] = {
        "generated_at": NOW,
        "service": None,
        "gps": GpsState.OK,
        "off_route": False,
        "finished": False,
        "stops": (),
        "total_waiting": 0,
        "free_places": None,
        "free_seats": None,
        "capacity_alert": False,
        "seat_alert": False,
    }
    return DriverView(**{**fields, **values})


async def settle() -> None:
    """Let the scheduled publications run: no time passes."""
    for _ in range(TURNS):
        await asyncio.sleep(0)


@dataclass
class FakeBuild:
    views: dict[str, DriverView] = field(default_factory=lambda: {SESSION: _view()})
    calls: list[str] = field(default_factory=list)
    gate: asyncio.Event | None = None
    error: Exception | None = None

    def open_session_ids(self) -> list[str]:
        return list(self.views)

    async def for_session_id(self, session_id: str) -> DriverView | None:
        self.calls.append(session_id)
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error
        return self.views.get(session_id)


class GatedSleep:
    """Waits until the test opens it, then moves the clock by what was asked."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.calls: list[float] = []
        self.gate = asyncio.Event()

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        await self.gate.wait()
        self.gate.clear()
        self.clock.advance(timedelta(seconds=seconds))


@dataclass
class Harness:
    clock: FakeClock = field(default_factory=lambda: FakeClock(NOW))
    build: FakeBuild = field(default_factory=FakeBuild)
    events: ChannelPublisher = field(default_factory=lambda: ChannelPublisher({CHANNEL: 1}))
    logger: RecordingLogger = field(default_factory=RecordingLogger)
    sleep: Any = None
    views: DemandViews = field(init=False)

    def __post_init__(self) -> None:
        self.sleep = self.sleep or GatedSleep(self.clock)
        self.views = DemandViews(
            self.build,  # type: ignore[arg-type]
            self.events,
            self.clock,
            logger=self.logger,
            sleep=self.sleep,
        )

    @property
    def published(self) -> list[DriverView | dict[str, object]]:
        return [e.payload for _, e in self.events.of_type(DRIVER_VIEW)]  # type: ignore[misc]


@pytest.fixture
async def harness() -> Any:
    built = Harness()
    yield built
    await built.views.aclose()


@pytest.mark.spec("driver_demand.AC-09")
async def test_a_touch_publishes_the_view_to_the_channel_of_the_shift(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()

    ((channel, event),) = harness.events.published
    assert channel == f"driver:{SESSION}"
    assert event.type == "driver.view"
    assert event.payload == driver_view_payload(harness.build.views[SESSION])


@pytest.mark.spec("driver_demand.AC-09")
async def test_touches_inside_the_second_are_grouped_into_one_view(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()

    for _ in range(4):
        harness.views.touch(SESSION)
        await settle()

    assert len(harness.published) == 1
    assert harness.sleep.calls == [1.0]

    harness.sleep.gate.set()
    await settle()

    assert len(harness.published) == 2
    assert harness.build.calls == [SESSION, SESSION]


@pytest.mark.spec("driver_demand.AC-09")
async def test_the_wait_is_only_what_is_left_of_the_second(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.clock.advance(timedelta(milliseconds=400))

    harness.views.touch(SESSION)
    await settle()

    assert harness.sleep.calls == [pytest.approx(0.6)]


@pytest.mark.spec("driver_demand.AC-09")
async def test_after_a_second_the_view_is_published_at_once(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.clock.advance(timedelta(seconds=1))

    harness.views.touch(SESSION)
    await settle()

    assert len(harness.published) == 2
    assert harness.sleep.calls == []


@pytest.mark.spec("driver_demand.AC-09")
async def test_each_shift_has_its_own_second(harness: Harness) -> None:
    harness.build.views["other"] = _view()
    harness.views.touch(SESSION)
    harness.views.touch("other")
    await settle()

    assert [channel for channel, _ in harness.events.published] == [
        CHANNEL,
        driver_channel("other"),
    ]


@pytest.mark.spec("driver_demand.AC-09")
async def test_the_published_view_has_the_latest_data(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.views.touch(SESSION)
    await settle()
    harness.build.views[SESSION] = _view(total_waiting=7)

    harness.sleep.gate.set()
    await settle()

    assert harness.published[-1]["total_waiting"] == 7  # type: ignore[index]


@pytest.mark.spec("driver_demand.AC-09")
async def test_a_touch_while_a_view_is_being_built_is_not_lost(harness: Harness) -> None:
    harness.build.gate = asyncio.Event()
    harness.views.touch(SESSION)
    await settle()
    harness.views.touch(SESSION)  # the data may have changed after the view started
    await settle()
    harness.build.gate.set()
    await settle()
    assert len(harness.published) == 1

    harness.sleep.gate.set()
    await settle()

    assert len(harness.published) == 2


@pytest.mark.spec("driver_demand.AC-09")
async def test_at_most_one_view_per_second_under_constant_touches() -> None:
    clock = FakeClock(NOW)

    async def sleep(seconds: float) -> None:
        clock.advance(timedelta(seconds=seconds))

    harness = Harness(clock=clock, sleep=sleep)
    instants = []
    original = harness.events.publish

    def publish(channel: str, event: Any) -> None:
        instants.append(clock.now())
        original(channel, event)

    harness.events.publish = publish  # type: ignore[method-assign]
    for _ in range(20):
        harness.views.touch(SESSION)
        await settle()
    await harness.views.aclose()

    assert len(instants) == 20
    assert all(b - a >= timedelta(seconds=1) for a, b in zip(instants, instants[1:], strict=False))


async def test_a_closed_shift_publishes_nothing(harness: Harness) -> None:
    del harness.build.views[SESSION]

    harness.views.touch(SESSION)
    await settle()

    assert harness.events.published == []


@pytest.mark.spec("driver_demand.AC-03")
async def test_forgetting_a_shift_cancels_its_pending_view(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.views.touch(SESSION)
    await settle()

    harness.views.forget(SESSION)
    harness.sleep.gate.set()
    await settle()

    assert len(harness.published) == 1
    assert harness.views.last_view(SESSION) is None


async def test_a_failure_only_logs_its_type_and_the_next_touch_works(harness: Harness) -> None:
    harness.build.error = RuntimeError("alert-1 device-1 secret")

    harness.views.touch(SESSION)
    await settle()

    assert harness.events.published == []
    ((event, fields),) = harness.logger.events
    assert event == "unhandled_exception"
    assert fields["error_type"] == "RuntimeError"
    assert "secret" not in repr(fields)

    harness.build.error = None
    harness.views.touch(SESSION)
    await settle()

    assert len(harness.published) == 1


@pytest.mark.spec("driver_demand.AC-12")
async def test_the_view_is_never_logged(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    await harness.views.refresh_all()
    await settle()

    assert harness.logger.events == []


@pytest.mark.spec("driver_demand.AC-09")
async def test_refresh_publishes_a_view_that_went_stale(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.clock.advance(timedelta(seconds=15))
    harness.build.views[SESSION] = _view(gps=GpsState.STALE, generated_at=harness.clock.now())

    await harness.views.refresh_all()
    await settle()

    assert harness.published[-1]["gps"] == "STALE"  # type: ignore[index]
    assert len(harness.published) == 2


@pytest.mark.spec("driver_demand.AC-09")
async def test_refresh_publishes_new_occupancy(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.clock.advance(timedelta(seconds=15))
    harness.build.views[SESSION] = _view(free_places=3, free_seats=1)

    await harness.views.refresh_all()
    await settle()

    assert harness.published[-1]["free_places"] == 3  # type: ignore[index]


@pytest.mark.spec("driver_demand.AC-09")
async def test_refresh_without_changes_publishes_nothing(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.clock.advance(timedelta(seconds=15))
    harness.build.views[SESSION] = _view(generated_at=harness.clock.now())

    await harness.views.refresh_all()
    await settle()

    assert len(harness.published) == 1


@pytest.mark.spec("driver_demand.AC-09")
async def test_refresh_only_builds_shifts_with_subscribers() -> None:
    harness = Harness(events=ChannelPublisher({}))

    await harness.views.refresh_all()
    await settle()

    assert harness.build.calls == []
    assert harness.events.published == []


@pytest.mark.spec("driver_demand.AC-09")
async def test_refresh_keeps_the_limit_of_one_view_per_second(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.build.views[SESSION] = _view(free_places=3)

    await harness.views.refresh_all()
    await settle()

    assert len(harness.published) == 1
    assert harness.sleep.calls == [1.0]


async def test_a_failing_shift_does_not_stop_the_refresh_of_the_others() -> None:
    other = driver_channel("other")
    harness = Harness(events=ChannelPublisher({CHANNEL: 1, other: 1}))
    harness.build.views["other"] = _view()
    original = harness.build.for_session_id

    async def flaky(session_id: str) -> DriverView | None:
        if session_id == SESSION:
            raise RuntimeError("boom")
        return await original(session_id)

    harness.build.for_session_id = flaky  # type: ignore[method-assign]

    await harness.views.refresh_all()
    await settle()

    assert [channel for channel, _ in harness.events.published] == [other]
    assert [fields["error_type"] for _, fields in harness.logger.events] == ["RuntimeError"]
    await harness.views.aclose()


@pytest.mark.spec("driver_demand.AC-05")
def test_the_payload_of_a_view_has_the_fields_of_the_design() -> None:
    departure = NOW - timedelta(minutes=5)
    view = _view(
        service=DriverServiceView(
            "93", 0, "Malva-rosa", TRIP, MONDAY, departure, "FE0000", "FFFFFF"
        ),
        stops=(
            StopDemand(
                "508",
                "Stop",
                12,
                640.5,
                2,
                NeedCounts(RAMP=1, SEAT=1),
                ("alert-1", "alert-2"),
            ),
        ),
        total_waiting=2,
        free_places=30,
        free_seats=4,
    )

    assert driver_view_payload(view) == {
        "generated_at": "2026-11-09T08:00:00Z",
        "service": {
            "line": "93",
            "direction_id": 0,
            "headsign": "Malva-rosa",
            "trip_id": TRIP,
            "service_date": "2026-11-09",
            "departure_at": "2026-11-09T07:55:00Z",
            "color": "FE0000",
            "text_color": "FFFFFF",
        },
        "gps": "OK",
        "off_route": False,
        "finished": False,
        "stops": [
            {
                "stop_id": "508",
                "name": "Stop",
                "stop_sequence": 12,
                "distance_m": 640.5,
                "waiting": 2,
                "needs": {"RAMP": 1, "EXTRA_TIME": 0, "SEAT": 1, "VISUAL": 0},
                "alert_ids": ["alert-1", "alert-2"],
            }
        ],
        "total_waiting": 2,
        "free_places": 30,
        "free_seats": 4,
        "capacity_alert": False,
        "seat_alert": False,
    }


@pytest.mark.spec("driver_demand.AC-07")
def test_the_payload_of_a_view_without_a_departure_has_a_null_service() -> None:
    assert driver_view_payload(_view())["service"] is None


# --- Listener and notifier -------------------------------------------------------------------


@dataclass
class FakeViews:
    last: DriverView | None = None
    touched: list[str] = field(default_factory=list)
    forgotten: list[str] = field(default_factory=list)
    log: list[str] | None = None

    def touch(self, session_id: str) -> None:
        self.touched.append(session_id)

    def last_view(self, session_id: str) -> DriverView | None:
        return self.last

    def forget(self, session_id: str) -> None:
        self.forgotten.append(session_id)
        if self.log is not None:
            self.log.append("forget")


STOPS = tuple((UpcomingStop(f"s{n}", f"Stop s{n}", n + 1, 0.0), float(n) * 500.0) for n in range(9))


class StubRoutes:
    def of(self, trip_id: str) -> TripRoute | None:
        return TripRoute((), (), STOPS) if trip_id == TRIP else None


@dataclass
class ListenerHarness:
    views: FakeViews = field(default_factory=FakeViews)
    events: ChannelPublisher = field(default_factory=ChannelPublisher)
    log: list[Any] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.views.log = self.log

    @property
    def listener(self) -> DemandSessionListener:
        def deliver(session: DriverSession, previous: DriverService | None) -> None:
            self.log.append(("deliver", session.session_id, previous))

        def undeliver(session_id: str) -> None:
            self.log.append(("undeliver", session_id))

        return DemandSessionListener(
            self.views,  # type: ignore[arg-type]
            deliver,  # type: ignore[arg-type]
            undeliver,  # type: ignore[arg-type]
            StubRoutes(),  # type: ignore[arg-type]
            self.events,
        )


def _position() -> DriverPosition:
    return DriverPosition(39.47, -0.37, 5.0, NOW)


def _running(progress_m: float = 200.0, **values: Any) -> DriverSession:
    return session_of(
        1,
        service=SERVICE,
        progress_m=progress_m,
        last_fix_at=NOW,
        position=_position(),
        **values,
    )


def _shown(*sequences: int, **values: Any) -> DriverView:
    stops = tuple(
        StopDemand(f"s{n - 1}", f"Stop s{n - 1}", n, 0.0, 0, NeedCounts(), ()) for n in sequences
    )
    return _view(stops=stops, **values)


SAME = (2, 3, 4, 5, 6)  # at 200 m the next five stops are s1…s5


@pytest.mark.spec("driver_demand.AC-09")
def test_a_position_that_changes_nothing_visible_does_not_touch() -> None:
    harness = ListenerHarness(FakeViews(last=_shown(*SAME)))

    harness.listener.position_updated(_running())

    assert harness.views.touched == []


@pytest.mark.spec("driver_demand.AC-09")
@pytest.mark.parametrize(
    ("last", "session"),
    [
        (None, _running()),  # nothing published yet
        (_shown(2, 3, 4, 5), _running()),  # other next stops
        (_shown(*SAME), _running(progress_m=900.0)),  # the bus passed a stop
        (_shown(*SAME), _running(off_route=True)),
        (_shown(*SAME, off_route=True), _running()),
        (_shown(*SAME, gps=GpsState.STALE), _running()),  # the GPS is back
        (_shown(*SAME, gps=GpsState.WAITING), _running()),  # first position
        (_shown(*SAME), _running(progress_m=4000.0)),  # finished
    ],
)
def test_a_position_that_changes_something_visible_touches(
    last: DriverView | None, session: DriverSession
) -> None:
    harness = ListenerHarness(FakeViews(last=last))

    harness.listener.position_updated(session)

    assert harness.views.touched == [SESSION]


@pytest.mark.spec("driver_demand.AC-09")
def test_a_finished_trip_that_is_already_shown_does_not_touch_again() -> None:
    harness = ListenerHarness(FakeViews(last=_view(finished=True)))

    harness.listener.position_updated(_running(progress_m=4000.0))

    assert harness.views.touched == []


@pytest.mark.spec("driver_demand.AC-09")
def test_a_shift_without_a_departure_only_touches_when_the_gps_changes() -> None:
    harness = ListenerHarness(FakeViews(last=_view()))
    session = session_of(1, last_fix_at=NOW, position=_position())

    harness.listener.position_updated(session)
    assert harness.views.touched == []

    harness.views.last = _view(gps=GpsState.WAITING)
    harness.listener.position_updated(session)
    assert harness.views.touched == [SESSION]


@pytest.mark.spec("driver_demand.AC-09")
def test_a_trip_gone_from_the_network_has_no_stops_to_compare() -> None:
    harness = ListenerHarness(FakeViews(last=_view()))
    session = replace(_running(), service=replace(SERVICE, trip_id="gone"))

    harness.listener.position_updated(session)

    assert harness.views.touched == []


@pytest.mark.spec("driver_demand.AC-02")
def test_choosing_a_departure_delivers_and_publishes_a_view() -> None:
    harness = ListenerHarness()
    session = session_of(1, service=SERVICE)
    previous = replace(SERVICE, trip_id="trip-0")

    harness.listener.service_selected(session, previous)

    assert harness.log == [("deliver", SESSION, previous)]
    assert harness.views.touched == [SESSION]


@pytest.mark.spec("driver_demand.AC-03")
@pytest.mark.parametrize("reason", list(SessionCloseReason))
def test_closing_returns_the_requests_and_tells_the_driver(reason: SessionCloseReason) -> None:
    harness = ListenerHarness()

    harness.listener.session_closed(SESSION, reason)

    assert harness.log == [("undeliver", SESSION), "forget"]
    assert harness.views.forgotten == [SESSION]
    ((channel, event),) = harness.events.published
    assert channel == CHANNEL
    assert event.type == SESSION_CLOSED
    assert event.message() == {"type": "session.closed", "reason": reason.value}


@pytest.mark.spec("driver_demand.AC-04")
def test_a_removed_request_publishes_a_view_to_its_shift() -> None:
    views = FakeViews()

    DemandViewNotifier(views).alert_removed(SESSION)  # type: ignore[arg-type]

    assert views.touched == [SESSION]


# --- Periodic refresh ------------------------------------------------------------------------


@pytest.mark.spec("driver_demand.AC-09")
async def test_the_refresh_task_runs_every_fifteen_seconds() -> None:
    assert VIEW_REFRESH_INTERVAL.total_seconds() == 15
    ticks: list[int] = []
    sleep = FakeSleep({15.0: 3})

    async def tick() -> None:
        ticks.append(1)

    tasks = start_demand_tasks(tick, VIEW_REFRESH_INTERVAL, RecordingLogger(), sleep=sleep)
    await settle()

    assert [task.get_name() for task in tasks] == [DEMAND_VIEW_REFRESHER]
    assert len(ticks) == 3
    await stop_tasks(tasks)
    assert all(task.done() for task in tasks)


async def test_aclose_cancels_the_pending_publications(harness: Harness) -> None:
    harness.views.touch(SESSION)
    await settle()
    harness.views.touch(SESSION)
    await settle()

    await harness.views.aclose()
    harness.sleep.gate.set()
    await settle()

    assert len(harness.published) == 1
