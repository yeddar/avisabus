"""`ExpireAlert` (effects of an expiry) and `ExpireDueAlerts` (`NEXT_STOP`, `TIMEOUT`) with fakes
of every port (alert_expiry T-02)."""

import json
from dataclasses import dataclass, field, replace
from datetime import timedelta

import pytest

from avisabus.application.expire_alert import ALERT_EXPIRED, ExpireAlert
from avisabus.application.expire_alerts import ExpireDueAlerts
from avisabus.domain.models.alert import Alert, AlertStatus, ExpiryReason
from avisabus.domain.models.events import Event
from avisabus.domain.ports.events import device_channel
from tests.support.alerts import FakeAlertRepository, RecordingLogger, RecordingPublisher
from tests.support.expiry import (
    ALERT_ID,
    AT_NEXT,
    DEVICE,
    NOW,
    RecordingNotifier,
    alert,
    network,
)
from tests.support.fake_clock import FakeClock
from tests.support.network import FakeNetwork

MARGIN = timedelta(minutes=2)
# alert(): last delay +60 s, so NEXT_STOP from AT_NEXT + 60 s + 2 min.
NEXT_STOP_DUE = AT_NEXT + timedelta(seconds=60) + MARGIN


@dataclass
class World:
    alerts: FakeAlertRepository = field(default_factory=FakeAlertRepository)
    events: RecordingPublisher = field(default_factory=RecordingPublisher)
    drivers: RecordingNotifier = field(default_factory=RecordingNotifier)
    logger: RecordingLogger = field(default_factory=RecordingLogger)
    network: FakeNetwork = field(default_factory=network)
    clock: FakeClock = field(default_factory=lambda: FakeClock(NOW))
    seen: dict[str, bool] = field(default_factory=dict)

    def store(self, *stored: Alert) -> None:
        for one in stored:
            self.alerts.alerts[one.alert_id] = one

    @property
    def expire(self) -> ExpireAlert:
        return ExpireAlert(self.alerts, self.events, self.drivers, self.logger)

    async def tick(self) -> None:
        ticker = ExpireDueAlerts(
            alerts=self.alerts,
            network=self.network,
            expire=self.expire,
            seen=lambda alert_id: self.seen.get(alert_id, False),
            clock=self.clock,
            next_stop_margin=MARGIN,
        )
        await ticker.tick()

    def expired(self) -> list[tuple[str, str]]:
        return [
            (str(e.payload["alert_id"]), str(e.payload["reason"])) for _, e in self.events.published
        ]


@pytest.fixture
def world() -> World:
    return World()


# --- Effects of an expiry (AC-08) ---


@pytest.mark.spec("alert_expiry.AC-08")
@pytest.mark.parametrize("reason", list(ExpiryReason))
def test_an_expired_alert_is_deleted_announced_and_logged(
    world: World, reason: ExpiryReason
) -> None:
    other = alert(alert_id="other", line="70")
    world.store(alert(), other)
    assert world.expire(alert(), reason) is True
    assert world.alerts.alerts == {"other": other}  # deleted with its needs
    assert world.events.published == [
        (device_channel(DEVICE), Event(ALERT_EXPIRED, {"alert_id": ALERT_ID, "reason": reason}))
    ]
    _, event = world.events.published[0]
    assert json.loads(json.dumps(event.message())) == {
        "type": "alert.expired",
        "alert_id": ALERT_ID,
        "reason": reason.value,
    }
    assert world.logger.events == [
        (
            "info",
            "alert.expired",
            {"alert_id": ALERT_ID, "stop_id": "508", "line": "93", "reason": reason.value},
        )
    ]
    assert world.drivers.removed == []  # PENDING_DRIVER: no driver view to refresh


@pytest.mark.spec("alert_expiry.AC-08")
def test_a_delivered_alert_refreshes_its_driver_view(world: World) -> None:
    delivered = alert(status=AlertStatus.DELIVERED, delivered_to="session-1")
    world.store(delivered)
    assert world.expire(delivered, ExpiryReason.PASSED) is True
    assert world.drivers.removed == ["session-1"]


@pytest.mark.spec("alert_expiry.AC-08")
def test_an_alert_already_gone_publishes_nothing(world: World) -> None:
    """Cancelled (or expired by the other task) in between: nothing to announce."""
    delivered = alert(status=AlertStatus.DELIVERED, delivered_to="session-1")
    assert world.expire(delivered, ExpiryReason.TIMEOUT) is False
    assert world.events.published == []
    assert world.drivers.removed == []
    assert world.logger.events == []


@pytest.mark.spec("alert_expiry.AC-08")
def test_the_expiry_log_carries_no_personal_data(world: World) -> None:
    world.store(alert())
    world.expire(alert(), ExpiryReason.NEXT_STOP)
    logged = json.dumps([fields for _, _, fields in world.logger.events])
    for secret in (DEVICE, "RAMP", "VISUAL", "needs", "device"):
        assert secret not in logged


# --- Next stop (AC-05) ---


@pytest.mark.spec("alert_expiry.AC-05")
async def test_an_alert_not_seen_expires_once_its_bus_should_be_at_the_next_stop(
    world: World,
) -> None:
    world.store(alert())
    world.clock.set(NEXT_STOP_DUE - timedelta(seconds=1))
    await world.tick()
    assert world.expired() == []
    world.clock.set(NEXT_STOP_DUE)
    await world.tick()
    assert world.expired() == [(ALERT_ID, "NEXT_STOP")]
    assert world.alerts.alerts == {}


@pytest.mark.spec("alert_expiry.AC-05")
async def test_an_alert_whose_trip_was_in_the_last_observation_does_not_expire_by_next_stop(
    world: World,
) -> None:
    world.store(alert())
    world.seen[ALERT_ID] = True
    world.clock.set(NEXT_STOP_DUE + timedelta(minutes=5))
    await world.tick()
    assert world.expired() == []
    world.seen[ALERT_ID] = False  # the next observation no longer has it
    await world.tick()
    assert world.expired() == [(ALERT_ID, "NEXT_STOP")]


@pytest.mark.spec("alert_expiry.AC-05")
async def test_the_last_observed_delay_is_used(world: World) -> None:
    late = replace(alert(), tracking=replace(alert().tracking, last_delay_s=600))
    world.store(late)
    world.clock.set(NEXT_STOP_DUE + timedelta(minutes=5))  # 9 min late would still be on time
    await world.tick()
    assert world.expired() == []
    world.clock.set(AT_NEXT + timedelta(seconds=600) + MARGIN)
    await world.tick()
    assert world.expired() == [(ALERT_ID, "NEXT_STOP")]


@pytest.mark.spec("alert_expiry.AC-05")
@pytest.mark.spec("alert_expiry.AC-06")
async def test_an_alert_at_the_last_stop_of_its_trip_only_times_out(world: World) -> None:
    last = alert(line="70", trip_id="70_071", stop_sequence=8)
    world.store(last)
    world.clock.set(last.expires_at - timedelta(seconds=1))
    await world.tick()
    assert world.expired() == []
    world.clock.set(last.expires_at)
    await world.tick()
    assert world.expired() == [(ALERT_ID, "TIMEOUT")]


@pytest.mark.spec("alert_expiry.AC-06")
async def test_an_alert_whose_trip_left_the_feed_only_times_out(world: World) -> None:
    gone = alert(trip_id="93_999")
    world.store(gone)
    world.clock.set(NEXT_STOP_DUE + timedelta(minutes=5))
    await world.tick()
    assert world.expired() == []
    world.clock.set(gone.expires_at)
    await world.tick()
    assert world.expired() == [(ALERT_ID, "TIMEOUT")]


# --- Timeout (AC-06) ---


@pytest.mark.spec("alert_expiry.AC-06")
async def test_every_alert_times_out_after_its_max_age(world: World) -> None:
    young = alert(alert_id="young", created_at=NOW, expires_at=NOW + timedelta(minutes=31))
    world.store(alert(), young)
    world.seen.update({ALERT_ID: True, "young": True})  # still seen: no NEXT_STOP
    world.clock.set(NOW + timedelta(minutes=30))
    await world.tick()
    assert world.expired() == [(ALERT_ID, "TIMEOUT")]
    assert set(world.alerts.alerts) == {"young"}


@pytest.mark.spec("alert_expiry.AC-06")
async def test_nothing_expires_before_its_time(world: World) -> None:
    world.store(alert())
    world.seen[ALERT_ID] = True
    await world.tick()
    world.clock.set(NOW + timedelta(minutes=29, seconds=59))
    await world.tick()
    assert world.expired() == []
    assert set(world.alerts.alerts) == {ALERT_ID}


# --- Priority (AC-07) ---


@pytest.mark.spec("alert_expiry.AC-07")
async def test_next_stop_comes_before_timeout(world: World) -> None:
    world.store(alert(expires_at=NEXT_STOP_DUE))
    world.clock.set(NEXT_STOP_DUE)
    await world.tick()
    assert world.expired() == [(ALERT_ID, "NEXT_STOP")]


@pytest.mark.spec("alert_expiry.AC-07")
async def test_an_alert_that_passed_in_the_same_cycle_is_not_expired_again(world: World) -> None:
    """The watcher expired it as `PASSED` first (same cycle): the ticker sees it no more, and an
    `ExpireAlert` racing with it publishes nothing."""
    world.store(alert())
    world.clock.set(alert().expires_at)
    assert world.expire(alert(), ExpiryReason.PASSED) is True
    await world.tick()
    assert world.expire(alert(), ExpiryReason.TIMEOUT) is False
    assert world.expired() == [(ALERT_ID, "PASSED")]


@pytest.mark.spec("alert_expiry.AC-06")
async def test_the_ticker_reads_the_injected_clock_once_per_cycle(world: World) -> None:
    calls: list[int] = []

    class CountingClock(FakeClock):
        def now(self):  # type: ignore[no-untyped-def]
            calls.append(1)
            return super().now()

    world.clock = CountingClock(alert().expires_at)
    world.store(alert(), alert(alert_id="b", line="70"), alert(alert_id="c", line="95"))
    world.seen.update({ALERT_ID: True, "b": True, "c": True})
    await world.tick()
    assert len(calls) == 1
    assert sorted(world.expired()) == [(ALERT_ID, "TIMEOUT"), ("b", "TIMEOUT"), ("c", "TIMEOUT")]
