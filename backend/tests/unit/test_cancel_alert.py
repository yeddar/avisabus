"""`CancelAlert` with fakes of the repository, the publisher, the driver notifier and the logger
(alert_cancel T-01)."""

import json
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta

import pytest

from avisabus.application.cancel_alert import ALERT_CANCELLED, CancelAlert
from avisabus.domain.errors import AlertNotFoundError, DomainError
from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking, Need
from avisabus.domain.models.events import Event
from avisabus.domain.ports.events import device_channel
from tests.support.alerts import FakeAlertRepository, RecordingLogger, RecordingPublisher

CREATED = datetime(2026, 11, 2, 19, 48, 3, tzinfo=UTC)
DEVICE = "d" * 64
OTHER_DEVICE = "e" * 64
ALERT_ID = "6f1c0d6e-3b9a-4c2e-9f4d-2a7b8c9d0e1f"


def alert(**changes: object) -> Alert:
    base = Alert(
        alert_id=ALERT_ID,
        device_hash=DEVICE,
        stop_id="508",
        stop_name="Parc de l'Oest - Enguera",
        line="93",
        direction_id=0,
        destination="Passeig Marítim - Hospital Malva-rosa",
        trip_id="93_122",
        service_date=date(2026, 11, 2),
        stop_sequence=12,
        needs=(Need.RAMP, Need.VISUAL),
        status=AlertStatus.PENDING_DRIVER,
        delivered_to=None,
        created_at=CREATED,
        expires_at=CREATED + timedelta(minutes=30),
        tracking=AlertTracking(None, CREATED + timedelta(minutes=7), 0),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


@dataclass
class RecordingNotifier:
    removed: list[str] = field(default_factory=list)

    def alert_removed(self, session_id: str) -> None:
        self.removed.append(session_id)


@dataclass
class ExpiringRepository(FakeAlertRepository):
    """The alert expires (another task deletes it) between `get` and `delete`."""

    def delete(self, alert_id: str) -> bool:
        self.alerts.pop(alert_id, None)
        return False


@dataclass
class World:
    alerts: FakeAlertRepository = field(default_factory=FakeAlertRepository)
    events: RecordingPublisher = field(default_factory=RecordingPublisher)
    drivers: RecordingNotifier = field(default_factory=RecordingNotifier)
    logger: RecordingLogger = field(default_factory=RecordingLogger)

    def store(self, *stored: Alert) -> None:
        for one in stored:
            self.alerts.alerts[one.alert_id] = one

    async def cancel(self, alert_id: str = ALERT_ID, device_hash: str = DEVICE) -> None:
        use_case = CancelAlert(self.alerts, self.events, self.drivers, self.logger)
        await use_case.execute(device_hash, alert_id)


@pytest.fixture
def world() -> World:
    return World()


# --- Cancellation (AC-01) ---


@pytest.mark.spec("alert_cancel.AC-01")
async def test_cancelling_deletes_the_alert_with_its_needs(world: World) -> None:
    other = alert(alert_id="other", line="70")
    world.store(alert(), other)
    await world.cancel()
    assert world.alerts.get(ALERT_ID) is None
    assert world.alerts.alerts == {"other": other}


@pytest.mark.spec("alert_cancel.AC-01")
async def test_cancelling_publishes_alert_cancelled_on_the_device_channel(world: World) -> None:
    world.store(alert())
    await world.cancel()
    assert world.events.published == [
        (device_channel(DEVICE), Event(ALERT_CANCELLED, {"alert_id": ALERT_ID}))
    ]
    _, event = world.events.published[0]
    assert event.message() == {"type": "alert.cancelled", "alert_id": ALERT_ID}


# --- Not found (AC-02) ---


@pytest.mark.spec("alert_cancel.AC-02")
@pytest.mark.parametrize(
    ("stored", "alert_id"),
    [
        pytest.param((), ALERT_ID, id="unknown"),
        pytest.param((), "not-a-uuid", id="not-a-uuid"),
        # Expired alerts are deleted by `alert_expiry`: it is just no longer there.
        pytest.param((alert(alert_id="other"),), ALERT_ID, id="expired"),
        pytest.param((alert(device_hash=OTHER_DEVICE),), ALERT_ID, id="other-device"),
    ],
)
async def test_a_missing_or_foreign_alert_is_not_found_and_nothing_changes(
    world: World, stored: tuple[Alert, ...], alert_id: str
) -> None:
    world.store(*stored)
    before = dict(world.alerts.alerts)
    with pytest.raises(AlertNotFoundError) as raised:
        await world.cancel(alert_id)
    assert isinstance(raised.value, DomainError)
    assert str(raised.value) == "alert not found"  # no identifiers in the message
    assert world.alerts.alerts == before
    assert world.events.published == []
    assert world.drivers.removed == []
    assert world.logger.named(ALERT_CANCELLED) == []


@pytest.mark.spec("alert_cancel.AC-02")
async def test_an_alert_that_expires_while_cancelling_is_not_found() -> None:
    world = World(alerts=ExpiringRepository())
    world.store(alert(status=AlertStatus.DELIVERED, delivered_to="session-7"))
    with pytest.raises(AlertNotFoundError):
        await world.cancel()
    assert world.events.published == []
    assert world.drivers.removed == []
    assert world.logger.named(ALERT_CANCELLED) == []


# --- Driver view (AC-04) ---


@pytest.mark.spec("alert_cancel.AC-04")
async def test_cancelling_a_delivered_alert_notifies_its_driver_view(world: World) -> None:
    world.store(alert(status=AlertStatus.DELIVERED, delivered_to="session-7"))
    await world.cancel()
    assert world.drivers.removed == ["session-7"]
    assert world.alerts.alerts == {}


@pytest.mark.spec("alert_cancel.AC-04")
async def test_cancelling_a_pending_alert_notifies_no_driver(world: World) -> None:
    world.store(alert())
    await world.cancel()
    assert world.drivers.removed == []
    assert world.alerts.alerts == {}


# --- Log (AC-05) ---


@pytest.mark.spec("alert_cancel.AC-05")
async def test_cancellation_is_logged_without_device_hash_nor_needs(world: World) -> None:
    world.store(alert(status=AlertStatus.DELIVERED, delivered_to="session-7"))
    await world.cancel()
    assert world.logger.events == [
        ("info", "alert.cancelled", {"alert_id": ALERT_ID, "stop_id": "508", "line": "93"})
    ]
    logged = json.dumps(world.logger.events)
    for secret in (DEVICE, "RAMP", "VISUAL", "needs", "session-7"):
        assert secret not in logged
