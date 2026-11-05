"""`WatchPassages` with a scripted `GetStopArrivals.for_stop` and fakes of every port, and
`GetStopArrivals.for_stop` itself (alert_expiry T-02)."""

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta

import pytest

from avisabus.application.expire_alert import ExpireAlert
from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from avisabus.application.watch_passages import WatchPassages
from avisabus.domain.errors import ArrivalsUnavailableError, NoActiveFeedError, StopNotFoundError
from avisabus.domain.models.alert import Alert, AlertTracking
from avisabus.domain.models.arrivals import ArrivalsSnapshot
from avisabus.domain.models.occupancy import OccupancyReading, OccupancyThresholds, VehicleRef
from avisabus.domain.models.stop_arrivals import ArrivalSource
from avisabus.domain.services.direction_resolver import DEFAULT_ALIASES
from tests.support.alerts import FakeAlertRepository, RecordingLogger, RecordingPublisher
from tests.support.expiry import (
    ALERT_ID,
    AT_508,
    NOW,
    RecordingNotifier,
    ScriptedStopArrivals,
    alert,
    arrival,
    network,
    observation,
)
from tests.support.fake_clock import FakeClock
from tests.support.network import FakeNetwork, FakeStopTokenSigner

WINDOW = timedelta(minutes=2)
T1 = NOW + timedelta(seconds=15)
T2 = NOW + timedelta(seconds=30)


@dataclass
class World:
    alerts: FakeAlertRepository = field(default_factory=FakeAlertRepository)
    stops: ScriptedStopArrivals = field(default_factory=ScriptedStopArrivals)
    events: RecordingPublisher = field(default_factory=RecordingPublisher)
    drivers: RecordingNotifier = field(default_factory=RecordingNotifier)
    logger: RecordingLogger = field(default_factory=RecordingLogger)
    network: FakeNetwork = field(default_factory=network)
    clock: FakeClock = field(default_factory=lambda: FakeClock(NOW))
    watcher: WatchPassages | None = None

    def store(self, *stored: Alert) -> None:
        for one in stored:
            self.alerts.alerts[one.alert_id] = one

    async def tick(self) -> None:
        if self.watcher is None:
            expire = ExpireAlert(self.alerts, self.events, self.drivers, self.logger)
            self.watcher = WatchPassages(
                alerts=self.alerts,
                stop_arrivals=self.stops,  # type: ignore[arg-type]
                network=self.network,
                expire=expire,
                clock=self.clock,
                logger=self.logger,
                passage_window=WINDOW,
            )
        await self.watcher.tick()

    def seen(self, alert_id: str = ALERT_ID) -> bool:
        assert self.watcher is not None
        return self.watcher.seen_in_last_observation(alert_id)

    def tracking(self, alert_id: str = ALERT_ID) -> AlertTracking:
        return self.alerts.alerts[alert_id].tracking

    def expired(self) -> list[tuple[str, str]]:
        return [
            (str(e.payload["alert_id"]), str(e.payload["reason"])) for _, e in self.events.published
        ]


@pytest.fixture
def world() -> World:
    return World()


def seen_at(lead: timedelta, at: datetime = NOW) -> AlertTracking:
    return AlertTracking(at, at + lead, 60)


# --- Tracking (AC-01, AC-09) ---


@pytest.mark.spec("alert_expiry.AC-01")
@pytest.mark.spec("alert_expiry.AC-09")
async def test_a_realtime_observation_with_the_trip_updates_its_stored_tracking(
    world: World,
) -> None:
    world.store(alert())
    arriving = AT_508 + timedelta(seconds=95)  # 95 s late at its occurrence 12
    world.stops.then(
        "508",
        observation(
            "508",
            T1,
            arrival("93_123", arriving - timedelta(minutes=4)),
            arrival("93_122", arriving),
        ),
    )
    await world.tick()
    assert world.tracking() == AlertTracking(
        last_seen_at=T1, last_arrival_at=arriving, last_delay_s=95
    )
    assert world.seen() is True
    assert world.expired() == []


@pytest.mark.spec("alert_expiry.AC-01")
async def test_the_trip_is_matched_by_trip_and_service_date(world: World) -> None:
    """The same trip of another service day is another bus."""
    world.store(alert(tracking=seen_at(timedelta(minutes=8))))
    yesterday = date(2026, 11, 1)
    world.stops.then("508", observation("508", T1, arrival("93_122", T1, service_date=yesterday)))
    await world.tick()
    assert world.tracking() == seen_at(timedelta(minutes=8))
    assert world.seen() is False


@pytest.mark.spec("alert_expiry.AC-01")
async def test_the_delay_is_rounded_to_whole_seconds(world: World) -> None:
    world.store(alert())
    arriving = AT_508 + timedelta(seconds=30, milliseconds=600)
    world.stops.then("508", observation("508", T1, arrival("93_122", arriving)))
    await world.tick()
    assert world.tracking().last_delay_s == 31


# --- Passage (AC-02) ---


@pytest.mark.spec("alert_expiry.AC-02")
async def test_a_trip_that_vanishes_while_arriving_has_passed(world: World) -> None:
    world.store(alert(), alert(alert_id="other", line="70", trip_id="70_071", stop_sequence=8))
    world.stops.then(
        "508",
        observation("508", T1, arrival("93_122", T1 + timedelta(minutes=2)), arrival("70_071", T1)),
        observation("508", T2, arrival("70_071", T2)),
    )
    await world.tick()
    assert world.expired() == []
    await world.tick()
    assert world.expired() == [(ALERT_ID, "PASSED")]
    assert set(world.alerts.alerts) == {"other"}
    assert world.logger.named("alert.expired") == [
        {"alert_id": ALERT_ID, "stop_id": "508", "line": "93", "reason": "PASSED"}
    ]


@pytest.mark.spec("alert_expiry.AC-02")
@pytest.mark.parametrize(
    "tracking",
    [
        pytest.param(seen_at(timedelta(minutes=3)), id="far-away"),
        pytest.param(AlertTracking(None, NOW + timedelta(minutes=1), 60), id="never-seen"),
    ],
)
async def test_a_trip_that_vanishes_far_away_or_never_seen_is_kept(
    world: World, tracking: AlertTracking
) -> None:
    world.store(alert(tracking=tracking))
    world.stops.then("508", observation("508", T1, arrival("93_123", T1 + timedelta(minutes=9))))
    await world.tick()
    assert world.expired() == []
    assert world.tracking() == tracking
    assert world.seen() is False
    assert world.logger.named("alert.trip_lost") == [{"alert_id": ALERT_ID, "stop_id": "508"}]
    assert [level for level, name, _ in world.logger.events if name == "alert.trip_lost"] == [
        "debug"
    ]


@pytest.mark.spec("alert_expiry.AC-02")
async def test_the_lead_counts_from_the_last_observation_instant(world: World) -> None:
    """Seen at T1 arriving in exactly 2 min (`generated_at` is the observation instant): the next
    observation without it is a passage."""
    world.store(alert(tracking=seen_at(timedelta(minutes=9))))
    world.stops.then(
        "508",
        observation("508", T1, arrival("93_122", T1 + WINDOW)),
        observation("508", T2),
    )
    await world.tick()
    assert world.tracking().last_seen_at == T1
    await world.tick()
    assert world.expired() == [(ALERT_ID, "PASSED")]


# --- Scheduled observations (AC-03) ---


@pytest.mark.spec("alert_expiry.AC-03")
async def test_a_scheduled_observation_neither_tracks_nor_passes(world: World) -> None:
    near = seen_at(timedelta(minutes=1))
    world.store(
        alert(tracking=near), alert(alert_id="b", line="70", tracking=near, trip_id="70_071")
    )
    world.stops.then(
        "508",
        # The timetable has the 93's trip (it would update the tracking) and not the 70's (it
        # would be a passage): neither counts.
        observation(
            "508", T1, arrival("93_122", T1 + timedelta(minutes=5)), source=ArrivalSource.SCHEDULED
        ),
    )
    await world.tick()
    assert world.expired() == []
    assert world.tracking() == near
    assert world.tracking("b") == near
    assert (world.seen(), world.seen("b")) == (False, False)


@pytest.mark.spec("alert_expiry.AC-03")
async def test_a_scheduled_observation_forgets_the_last_realtime_one(world: World) -> None:
    world.store(alert(tracking=seen_at(timedelta(minutes=9))))
    world.stops.then(
        "508",
        observation("508", NOW, arrival("93_122", NOW + timedelta(minutes=9))),
        observation("508", T1, source=ArrivalSource.SCHEDULED),
    )
    await world.tick()
    assert world.seen() is True
    await world.tick()
    assert world.seen() is False


# --- One query per stop (AC-04) ---


@pytest.mark.spec("alert_expiry.AC-04")
async def test_each_stop_with_alerts_is_queried_once_per_cycle(world: World) -> None:
    world.store(
        alert(),
        alert(alert_id="b", device_hash="e" * 64),
        alert(alert_id="c", line="70", trip_id="70_071", stop_sequence=8),
        alert(alert_id="d", stop_id="2070", stop_sequence=13),
    )
    for _ in range(2):
        world.stops.then(
            "508", observation("508", T1, arrival("93_122", T1 + timedelta(minutes=8)))
        )
        world.stops.then(
            "2070", observation("2070", T1, arrival("93_122", T1 + timedelta(minutes=9)))
        )
    await world.tick()
    assert sorted(world.stops.calls) == ["2070", "508"]
    await world.tick()
    assert sorted(world.stops.calls) == ["2070", "2070", "508", "508"]


@pytest.mark.spec("alert_expiry.AC-04")
async def test_without_alerts_nothing_is_queried(world: World) -> None:
    await world.tick()
    assert world.stops.calls == []


# --- Skipped stops ---


@pytest.mark.parametrize("error", [StopNotFoundError("508"), NoActiveFeedError()])
async def test_a_stop_that_cannot_be_read_is_skipped_and_logged(
    world: World, error: Exception
) -> None:
    world.store(alert(), alert(alert_id="d", stop_id="2070", stop_sequence=13))
    world.stops.then("508", error)
    world.stops.then("2070", observation("2070", T1))
    await world.tick()
    assert world.logger.named("passage.stop_skipped") == [
        {"stop_id": "508", "error_type": type(error).__name__}
    ]
    assert world.logger.named("alert.trip_lost") == [{"alert_id": "d", "stop_id": "2070"}]
    assert world.expired() == []


async def test_other_errors_reach_the_periodic_task(world: World) -> None:
    world.store(alert())
    world.stops.then("508", RuntimeError("database is locked"))
    with pytest.raises(RuntimeError):
        await world.tick()


# --- What the ticker reads (AC-05) ---


@pytest.mark.spec("alert_expiry.AC-05")
async def test_seen_in_last_observation(world: World) -> None:
    world.store(alert())
    world.stops.then(
        "508",
        observation("508", NOW, arrival("93_122", NOW + timedelta(minutes=9))),
        observation("508", T1),
    )
    await world.tick()
    assert (world.seen(), world.seen("unknown")) == (True, False)
    await world.tick()  # absent far away: kept, but not seen
    assert world.seen() is False
    assert ALERT_ID in world.alerts.alerts


@pytest.mark.spec("alert_expiry.AC-05")
async def test_seen_is_forgotten_with_the_alert(world: World) -> None:
    world.store(alert())
    world.stops.then("508", observation("508", NOW, arrival("93_122", NOW + timedelta(minutes=9))))
    await world.tick()
    del world.alerts.alerts[ALERT_ID]  # cancelled
    await world.tick()
    assert world.watcher is not None
    assert world.seen() is False
    assert world.watcher._seen == {}  # no memory left behind


@pytest.mark.spec("alert_expiry.AC-01")
async def test_a_present_trip_whose_occurrence_left_the_feed_keeps_its_delay(
    world: World,
) -> None:
    world.store(alert(stop_sequence=99))
    world.stops.then("508", observation("508", T1, arrival("93_122", T1 + timedelta(minutes=4))))
    await world.tick()
    assert world.tracking() == AlertTracking(T1, T1 + timedelta(minutes=4), 60)


# --- GetStopArrivals.for_stop ---


@dataclass
class CountingSource:
    calls: list[str] = field(default_factory=list)
    error: str | None = None

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        self.calls.append(stop_id)
        if self.error is not None:
            raise ArrivalsUnavailableError(stop_id, self.error)
        return ArrivalsSnapshot(stop_id=stop_id, fetched_at=NOW, arrivals=())


class NoOccupancy:
    async def read(self, vehicle: VehicleRef, at: datetime) -> OccupancyReading | None:
        return None


def get_stop_arrivals(fake: FakeNetwork, source: CountingSource) -> GetStopArrivals:
    return GetStopArrivals(
        network=fake,
        signer=FakeStopTokenSigner(),
        arrivals=source,
        scheduled=ScheduledArrivalsProvider(fake),
        occupancy=NoOccupancy(),
        thresholds=OccupancyThresholds(),
        clock=FakeClock(NOW),
        refresh_after_s=20,
        match_tolerance=timedelta(minutes=10),
        aliases=DEFAULT_ALIASES,
        direction_overrides={},
        min_score=0.2,
        alert_max_lead=timedelta(minutes=30),
        logger=RecordingLogger(),
    )


@pytest.mark.spec("alert_expiry.AC-04")
async def test_for_stop_reads_the_arrivals_without_a_token() -> None:
    source = CountingSource()
    result = await get_stop_arrivals(network(), source).for_stop("508")
    assert (result.stop_id, result.source, result.generated_at) == (
        "508",
        ArrivalSource.REALTIME,
        NOW,
    )
    assert source.calls == ["508"]


@pytest.mark.spec("alert_expiry.AC-03")
async def test_for_stop_falls_back_to_the_timetable_like_execute() -> None:
    source = CountingSource(error="timeout")
    result = await get_stop_arrivals(network(), source).for_stop("508")
    assert result.source is ArrivalSource.SCHEDULED


async def test_for_stop_of_a_stop_no_longer_in_the_network() -> None:
    source = CountingSource()
    with pytest.raises(StopNotFoundError):
        await get_stop_arrivals(network(), source).for_stop("99999")
    without_feed = replace(network(), feed=None)
    with pytest.raises(NoActiveFeedError):
        await get_stop_arrivals(without_feed, source).for_stop("508")
    assert source.calls == []
