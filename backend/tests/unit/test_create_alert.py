"""`CreateAlert`, `ListMyAlerts` and `alert_payload` with fakes of every port (T-04)."""

import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from avisabus.adapters.outbound.drivers.no_driver_directory import NoDriverDirectory
from avisabus.adapters.outbound.drivers.noop_notifier import NoopDriverViewNotifier
from avisabus.application.alert_events import (
    ALERT_DELIVERED,
    ALERT_REGISTERED,
    alert_event,
    alert_payload,
)
from avisabus.application.create_alert import CreateAlert, CreateAlertCommand
from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.application.list_my_alerts import ListMyAlerts
from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from avisabus.domain.errors import (
    ArrivalsUnavailableError,
    BusNotRequestableError,
    NoActiveFeedError,
    RateLimitedError,
    StopNotFoundError,
)
from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking, Need
from avisabus.domain.models.arrivals import ArrivalKind, ArrivalsSnapshot, SaeArrival
from avisabus.domain.models.network import TripStopTime
from avisabus.domain.models.occupancy import OccupancyReading, OccupancyThresholds, VehicleRef
from avisabus.domain.ports.alerts import DriverRef
from avisabus.domain.ports.events import device_channel
from avisabus.domain.services.direction_resolver import DEFAULT_ALIASES
from avisabus.domain.services.occupancy_simulation import service_day_start
from tests.support.alerts import (
    FakeAlertRepository,
    FakeDriverDirectory,
    RecordingLimiter,
    RecordingLogger,
    RecordingPublisher,
)
from tests.support.fake_clock import FakeClock
from tests.support.network import FakeNetwork, FakeStopTokenSigner, line_direction

NOW = datetime(2026, 11, 2, 19, 48, 3, tzinfo=UTC)  # 20:48:03 in València (Monday)
DAY = date(2026, 11, 2)
SIGNER = FakeStopTokenSigner()
TOKEN = SIGNER.sign("508")
DEVICE = "d" * 64
IP = "192.0.2.10"
HEADSIGN_93 = "Passeig Marítim - Hospital Malva-rosa"
MAX_AGE = timedelta(minutes=30)


def at(minutes: float) -> datetime:
    return NOW + timedelta(minutes=minutes)


def sae(line: str, destination: str, minutes: int) -> SaeArrival:
    return SaeArrival(line, destination, ArrivalKind.MINUTES, minutes, at(minutes))


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
    alerts: FakeAlertRepository = field(default_factory=FakeAlertRepository)
    drivers: FakeDriverDirectory = field(default_factory=FakeDriverDirectory)
    device_limiter: RecordingLimiter = field(default_factory=RecordingLimiter)
    ip_limiter: RecordingLimiter = field(default_factory=RecordingLimiter)
    events: RecordingPublisher = field(default_factory=RecordingPublisher)
    logger: RecordingLogger = field(default_factory=RecordingLogger)

    def use_case(self) -> CreateAlert:
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
            alert_max_lead=timedelta(minutes=30),
            logger=SilentLogger(),
        )
        return CreateAlert(
            stop_arrivals=stop_arrivals,
            network=self.network,
            alerts=self.alerts,
            drivers=self.drivers,
            device_limiter=self.device_limiter,
            ip_limiter=self.ip_limiter,
            events=self.events,
            clock=self.clock,
            max_age=MAX_AGE,
            logger=self.logger,
        )

    async def execute(self, **changes: Any) -> Any:
        return await self.use_case().execute(replace(command(), **changes))

    @property
    def device_attempts(self) -> int:
        return self.device_limiter.count(f"device:{DEVICE}")

    @property
    def ip_attempts(self) -> int:
        return self.ip_limiter.count(f"ip:{IP}")


def command() -> CreateAlertCommand:
    return CreateAlertCommand(
        device_hash=DEVICE,
        client_ip=IP,
        stop_id="508",
        token=TOKEN,
        line="93",
        direction_id=0,
        trip_id="93_122",
        service_date=DAY,
        needs=(Need.RAMP, Need.VISUAL),
    )


@pytest.fixture
def world() -> World:
    network = FakeNetwork()
    network.add_line("93")
    network.add_line("70")
    network.add_stop(
        "508",
        "Parc de l'Oest - Enguera",
        line_direction("70", 1, "Alboraia"),
        line_direction("93", 0, HEADSIGN_93),
    )
    network.add_headsign("508", "93", 0, HEADSIGN_93)
    network.add_headsign("508", "70", 1, "Alboraia")
    for suffix, when in (
        ("122", datetime(2026, 11, 2, 19, 50, 35, tzinfo=UTC)),
        ("123", datetime(2026, 11, 2, 19, 59, 8, tzinfo=UTC)),
        ("124", datetime(2026, 11, 2, 20, 8, 8, tzinfo=UTC)),
    ):
        network.add_passage("508", f"93_{suffix}", "93", 0, HEADSIGN_93, when, DAY)
    network.add_passage("508", "70_a", "70", 1, "Alboraia", at(3), DAY)
    network.add_passage("508", "70_b", "70", 1, "Alboraia", at(40), DAY)
    # 93 in 7 and 8 min (trips _122 and _123), 70 in 2 (70_a) and 38 min (70_b, too far ahead).
    source = FakeArrivalsSource(
        (
            sae("93", "Pass. Marítim", 7),
            sae("93", "Pass. Marítim", 8),
            sae("70", "Alboraia", 2),
            sae("70", "Alboraia", 38),
        )
    )
    return World(network, source, FakeClock(NOW))


def _texts(logger: RecordingLogger) -> str:
    return json.dumps([fields for _, _, fields in logger.events])


# --- Creation and confirmation ---


@pytest.mark.spec("alert_create.AC-09")
async def test_without_driver_the_alert_is_registered_and_announced(world: World) -> None:
    result = await world.execute()
    alert = result.alert
    assert result.created is True
    assert uuid.UUID(alert.alert_id).version == 4
    assert alert == Alert(
        alert_id=alert.alert_id,
        device_hash=DEVICE,
        stop_id="508",
        stop_name="Parc de l'Oest - Enguera",
        line="93",
        direction_id=0,
        destination=HEADSIGN_93,
        trip_id="93_122",
        service_date=DAY,
        stop_sequence=5,
        needs=(Need.RAMP, Need.VISUAL),
        status=AlertStatus.PENDING_DRIVER,
        delivered_to=None,
        created_at=NOW,
        expires_at=NOW + MAX_AGE,
        # Seen now in the SAE, 7 min ahead; scheduled at 19:50:35 → 268 s late.
        tracking=AlertTracking(last_seen_at=NOW, last_arrival_at=at(7), last_delay_s=268),
    )
    assert world.alerts.list_all() == [alert]
    assert world.drivers.queries == [("93", 0, "93_122", DAY)]
    assert world.events.published == [
        (device_channel(DEVICE), alert_event(ALERT_REGISTERED, alert))
    ]
    (channel, event) = world.events.published[0]
    assert event.type == "alert.registered"
    assert event.payload == {"alert": alert_payload(alert)}


@pytest.mark.spec("alert_create.AC-09")
async def test_with_a_driver_the_alert_is_delivered(world: World) -> None:
    world.drivers.driver = DriverRef("session-7")
    alert = (await world.execute()).alert
    assert (alert.status, alert.delivered_to) == (AlertStatus.DELIVERED, "session-7")
    assert world.events.published == [(device_channel(DEVICE), alert_event(ALERT_DELIVERED, alert))]
    assert world.events.published[0][1].type == "alert.delivered"
    assert world.logger.named("alert.created")[0]["status"] == "DELIVERED"


@pytest.mark.spec("alert_create.AC-06")
async def test_needs_are_kept_in_canonical_order(world: World) -> None:
    alert = (await world.execute(needs=(Need.VISUAL, Need.SEAT, Need.RAMP))).alert
    assert alert.needs == (Need.RAMP, Need.SEAT, Need.VISUAL)
    assert (
        await world.execute(line="70", trip_id="70_a", direction_id=1, needs=())
    ).alert.needs == ()


async def test_scheduled_arrival_has_never_been_seen_in_real_time(world: World) -> None:
    world.source.error = "timeout"
    alert = (await world.execute()).alert
    scheduled = datetime(2026, 11, 2, 19, 50, 35, tzinfo=UTC)
    assert alert.tracking == AlertTracking(
        last_seen_at=None, last_arrival_at=scheduled, last_delay_s=0
    )


async def test_circular_trip_uses_the_occurrence_closest_to_the_arrival(world: World) -> None:
    start = service_day_start(DAY)
    first = int((at(-50) - start).total_seconds())
    second = int((at(6.5) - start).total_seconds())  # 30 s before the SAE's 7 min
    world.network.trips["93_122"] = [
        TripStopTime("508", 1, first, first, None),
        TripStopTime("x", 2, first + 600, first + 600, None),
        TripStopTime("508", 3, second, second, None),
    ]
    alert = (await world.execute()).alert
    assert (alert.stop_sequence, alert.tracking.last_delay_s) == (3, 30)


async def test_delay_is_rounded_to_whole_seconds(world: World) -> None:
    world.source.arrivals = (
        SaeArrival("93", "Pass. Marítim", ArrivalKind.MINUTES, 7, at(7) + timedelta(seconds=0.6)),
        sae("93", "Pass. Marítim", 8),
    )
    assert (await world.execute()).alert.tracking.last_delay_s == 269


async def test_alerts_of_other_lines_of_the_stop_are_independent(world: World) -> None:
    first = await world.execute()
    second = await world.execute(line="70", direction_id=1, trip_id="70_a")
    assert (first.created, second.created) == (True, True)
    assert second.alert.destination == "Alboraia"
    assert len(world.alerts.list_all()) == 2


# --- The bus must be requestable (AC-03) ---


@pytest.mark.spec("alert_create.AC-03")
@pytest.mark.parametrize(
    "changes",
    [
        {"trip_id": "93_999"},  # no such bus
        {"trip_id": "93_124"},  # a bus the SAE does not show (it already passed or is far away)
        {"service_date": date(2026, 11, 1)},  # same trip, another service day
        {"direction_id": 1},  # another direction
        {"line": "70", "direction_id": 1, "trip_id": "70_b"},  # 38 min ahead: can_alert false
        {"line": "70", "direction_id": 1, "trip_id": "93_122"},  # trip of another line
    ],
)
async def test_bus_not_requestable_creates_nothing(world: World, changes: dict[str, Any]) -> None:
    with pytest.raises(BusNotRequestableError):
        await world.execute(**changes)
    assert world.alerts.list_all() == []
    assert world.events.published == []
    assert world.drivers.queries == []
    assert world.source.calls == ["508"]  # only the arrivals of GetStopArrivals
    assert world.logger.named("alert.rejected") == [
        {"reason": "bus_not_requestable", "stop_id": "508"}
    ]
    assert world.logger.named("alert.created") == []
    # The request counts towards the limits (AC-08).
    assert (world.device_attempts, world.ip_attempts) == (1, 1)


@pytest.mark.spec("alert_create.AC-03")
async def test_trip_no_longer_calling_at_the_stop_is_not_requestable(world: World) -> None:
    world.network.trips["93_122"] = [TripStopTime("elsewhere", 1, 0, 0, None)]
    with pytest.raises(BusNotRequestableError):
        await world.execute()
    assert world.alerts.list_all() == []


@pytest.mark.spec("alert_create.AC-04")
async def test_invalid_token_or_unknown_stop_never_asks_the_sae(world: World) -> None:
    with pytest.raises(StopNotFoundError):
        await world.execute(token="nope")  # noqa: S106 - not a password
    with pytest.raises(StopNotFoundError):
        await world.execute(stop_id="999", token=SIGNER.sign("999"))
    assert world.source.calls == []
    assert world.alerts.list_all() == []
    assert world.events.published == []


async def test_stop_removed_by_a_new_feed_in_between(world: World) -> None:
    class StopVanishes(FakeNetwork):
        def get_stop(self, stop_id: str) -> Any:
            # Present while the arrivals check the token, gone right after.
            found = super().get_stop(stop_id)
            self.stops.pop(stop_id, None)
            return found

    vanishing = StopVanishes(**{f: getattr(world.network, f) for f in vars(world.network)})
    world.network = vanishing
    with pytest.raises(StopNotFoundError):
        await world.execute()
    assert world.alerts.list_all() == []


async def test_no_active_feed(world: World) -> None:
    world.network.feed = None
    with pytest.raises(NoActiveFeedError):
        await world.execute()
    assert world.source.calls == []


# --- Uniqueness (AC-07) ---


@pytest.mark.spec("alert_create.AC-07")
async def test_existing_alert_at_the_stop_and_line_is_returned_unchanged(world: World) -> None:
    first = (await world.execute()).alert
    world.events.published.clear()
    world.clock.advance(timedelta(minutes=1))
    again = await world.execute(trip_id="93_123", needs=(Need.SEAT,))  # another bus of the 93
    assert (again.created, again.alert) == (False, first)
    assert world.alerts.list_all() == [first]
    assert world.events.published == []
    assert world.source.calls == ["508"]  # checked before asking for the arrivals
    assert world.drivers.queries == [("93", 0, "93_122", DAY)]
    # A 200 does not count towards the limits (AC-08).
    assert (world.device_attempts, world.ip_attempts) == (1, 1)
    assert world.logger.named("alert.duplicate") == [{"stop_id": "508", "line": "93"}]
    assert ("debug", "alert.duplicate") in [(lvl, ev) for lvl, ev, _ in world.logger.events]


@pytest.mark.spec("alert_create.AC-07")
async def test_a_concurrent_request_that_stored_first_wins(world: World) -> None:
    winner = replace((await world.execute()).alert, alert_id=str(uuid.uuid4()))
    world.alerts.alerts.clear()
    world.events.published.clear()
    world.alerts.race = winner
    result = await world.execute()
    assert (result.created, result.alert) == (False, winner)
    assert world.alerts.list_all() == [winner]
    assert world.events.published == []
    assert (world.device_attempts, world.ip_attempts) == (1, 1)
    assert len(world.logger.named("alert.created")) == 1


# --- Limits (AC-08) ---


@pytest.mark.spec("alert_create.AC-08")
@pytest.mark.parametrize(
    ("device_retry", "ip_retry", "expected"), [(42, None, 42), (None, 7, 7), (42, 300, 300)]
)
async def test_rate_limited_requests_are_rejected_before_anything_else(
    world: World, device_retry: int | None, ip_retry: int | None, expected: int
) -> None:
    world.device_limiter.retry_after = device_retry
    world.ip_limiter.retry_after = ip_retry
    with pytest.raises(RateLimitedError) as raised:
        await world.execute()
    assert raised.value.retry_after_s == expected
    assert world.source.calls == []
    assert world.alerts.list_all() == []
    assert world.events.published == []
    assert world.logger.named("alert.rejected") == [{"reason": "rate_limited", "stop_id": "508"}]
    # Both limiters see every attempt, keyed by device hash and by IP.
    assert (world.device_attempts, world.ip_attempts) == (1, 1)
    assert world.device_limiter.attempts[f"device:{DEVICE}"] == [NOW]


@pytest.mark.spec("alert_create.AC-08")
async def test_rate_limit_applies_before_the_duplicate_check(world: World) -> None:
    await world.execute()
    world.device_limiter.retry_after = 5
    with pytest.raises(RateLimitedError):
        await world.execute()


# --- Logs (AC-13) ---


@pytest.mark.spec("alert_create.AC-13")
async def test_logs_never_carry_the_device_the_ip_nor_the_needs(world: World) -> None:
    alert = (await world.execute(needs=(Need.RAMP, Need.EXTRA_TIME, Need.SEAT, Need.VISUAL))).alert
    assert world.logger.named("alert.created") == [
        {
            "alert_id": alert.alert_id,
            "stop_id": "508",
            "line": "93",
            "direction_id": 0,
            "status": "PENDING_DRIVER",
        }
    ]
    await world.execute()  # duplicate
    with pytest.raises(BusNotRequestableError):
        await world.execute(line="70", direction_id=1, trip_id="70_b")
    world.ip_limiter.retry_after = 3
    with pytest.raises(RateLimitedError):
        await world.execute()
    logged = _texts(world.logger)
    for secret in (DEVICE, IP, "RAMP", "EXTRA_TIME", "SEAT", "VISUAL", "needs"):
        assert secret not in logged
    assert {name for _, name, _ in world.logger.events} == {
        "alert.created",
        "alert.duplicate",
        "alert.rejected",
    }


# --- Payload and listing (AC-02, AC-10) ---


@pytest.mark.spec("alert_create.AC-02")
async def test_alert_payload_is_the_public_schema(world: World) -> None:
    alert = (await world.execute()).alert
    assert alert_payload(alert) == {
        "alert_id": alert.alert_id,
        "stop_id": "508",
        "stop_name": "Parc de l'Oest - Enguera",
        "line": "93",
        "direction_id": 0,
        "destination": HEADSIGN_93,
        "trip_id": "93_122",
        "service_date": "2026-11-02",
        "needs": ["RAMP", "VISUAL"],
        "status": "PENDING_DRIVER",
        "created_at": "2026-11-02T19:48:03Z",
        "expires_at": "2026-11-02T20:18:03Z",
    }
    json.dumps(alert_payload(alert))  # JSON serialisable as it is


def test_alert_payload_keeps_microseconds_in_utc() -> None:
    created = datetime(2026, 11, 2, 19, 48, 3, 250000, tzinfo=UTC)
    alert = Alert(
        alert_id="a",
        device_hash=DEVICE,
        stop_id="508",
        stop_name="n",
        line="93",
        direction_id=0,
        destination="d",
        trip_id="t",
        service_date=DAY,
        stop_sequence=1,
        needs=(),
        status=AlertStatus.DELIVERED,
        delivered_to="s",
        created_at=created,
        expires_at=created + MAX_AGE,
        tracking=AlertTracking(None, created, 0),
    )
    payload = alert_payload(alert)
    assert payload["created_at"] == "2026-11-02T19:48:03.250000Z"
    assert payload["needs"] == []
    assert "device_hash" not in payload and "delivered_to" not in payload


@pytest.mark.spec("alert_create.AC-10")
async def test_list_my_alerts_returns_the_device_alerts_by_creation(world: World) -> None:
    first = (await world.execute()).alert
    world.clock.advance(timedelta(seconds=30))
    second = (await world.execute(line="70", direction_id=1, trip_id="70_a")).alert
    other = replace(first, alert_id="other", device_hash="e" * 64)
    world.alerts.alerts[other.alert_id] = other
    list_my_alerts = ListMyAlerts(world.alerts)
    assert await list_my_alerts.execute(DEVICE) == [first, second]
    assert await list_my_alerts.execute("f" * 64) == []


# --- Block 3 adapters ---


@pytest.mark.spec("alert_create.AC-09")
def test_block_3_has_no_drivers() -> None:
    assert NoDriverDirectory().find_driver("93", 0, "93_122", DAY) is None
    assert NoopDriverViewNotifier().alert_removed("session-1") is None
