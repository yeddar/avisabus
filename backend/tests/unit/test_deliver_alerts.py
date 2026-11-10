"""Delivery of the stop requests to the driver of their bus (driver_demand T-02)."""

from dataclasses import dataclass, field, replace
from datetime import timedelta

import pytest

from avisabus.adapters.outbound.drivers.session_directory import SessionDriverDirectory
from avisabus.application.alert_events import alert_payload
from avisabus.application.deliver_alerts import (
    DeliverPendingAlerts,
    DeliveryObservingAlerts,
    UndeliverSessionAlerts,
    UndeliveryReason,
)
from avisabus.domain.models.alert import Alert, AlertStatus, Need
from avisabus.domain.models.driver import DriverService
from avisabus.domain.ports.alerts import AlertRepository, DriverRef
from avisabus.domain.ports.events import device_channel
from tests.support.alerts import FakeAlertRepository, RecordingPublisher
from tests.support.demand import MONDAY, SESSION, TRIP, alert_at
from tests.support.drivers import InMemorySessions, RecordingLogger, session_of

SERVICE = DriverService("93", 0, TRIP, MONDAY)
OTHER_SERVICE = DriverService("93", 0, "trip-2", MONDAY)


def _pending(number: int, **values: object) -> Alert:
    values.setdefault("needs", (Need.RAMP,))
    return alert_at(  # type: ignore[arg-type]
        number, status=AlertStatus.PENDING_DRIVER, delivered_to=None, **values
    )


@dataclass
class Harness:
    alerts: FakeAlertRepository = field(default_factory=FakeAlertRepository)
    events: RecordingPublisher = field(default_factory=RecordingPublisher)
    logger: RecordingLogger = field(default_factory=RecordingLogger)

    def add(self, *alerts: Alert) -> None:
        self.alerts.alerts.update({alert.alert_id: alert for alert in alerts})

    @property
    def undeliver(self) -> UndeliverSessionAlerts:
        return UndeliverSessionAlerts(self.alerts, self.events, self.logger)

    @property
    def deliver(self) -> DeliverPendingAlerts:
        return DeliverPendingAlerts(self.alerts, self.events, self.undeliver, self.logger)

    def stored(self, alert_id: str) -> Alert:
        return self.alerts.alerts[alert_id]

    def event_of(self, number: int) -> tuple[str, dict[str, object]]:
        """Type and body of the only event published to the device of the alert."""
        channel = device_channel(f"device-{number}")
        (event,) = [e for c, e in self.events.published if c == channel]
        return event.type, dict(event.payload)


@pytest.fixture
def harness() -> Harness:
    return Harness()


@pytest.mark.spec("driver_demand.AC-02")
def test_choosing_a_departure_delivers_its_pending_requests(harness: Harness) -> None:
    harness.add(_pending(1), _pending(2), _pending(3, trip_id="trip-2"))

    harness.deliver(session_of(1, service=SERVICE), None)

    for number in (1, 2):
        alert = harness.stored(f"alert-{number}")
        assert (alert.status, alert.delivered_to) == (AlertStatus.DELIVERED, SESSION)
        assert harness.event_of(number) == ("alert.delivered", {"alert": alert_payload(alert)})
        assert harness.event_of(number)[1]["alert"]["status"] == "DELIVERED"  # type: ignore[index]
    untouched = harness.stored("alert-3")
    assert (untouched.status, untouched.delivered_to) == (AlertStatus.PENDING_DRIVER, None)


@pytest.mark.spec("driver_demand.AC-02")
def test_the_same_trip_of_another_service_day_is_not_delivered(harness: Harness) -> None:
    harness.add(_pending(1, service_date=MONDAY + timedelta(days=1)))

    harness.deliver(session_of(1, service=SERVICE), None)

    assert harness.stored("alert-1").status is AlertStatus.PENDING_DRIVER
    assert harness.events.published == []


@pytest.mark.spec("driver_demand.AC-02")
def test_requests_already_delivered_are_not_delivered_again(harness: Harness) -> None:
    harness.add(alert_at(1))

    harness.deliver(session_of(1, service=SERVICE), SERVICE)

    assert harness.events.published == []


@pytest.mark.spec("driver_demand.AC-02")
def test_changing_departure_returns_the_old_requests_and_takes_the_new_ones(
    harness: Harness,
) -> None:
    harness.add(alert_at(1), _pending(2, trip_id="trip-2"))

    harness.deliver(session_of(1, service=OTHER_SERVICE), SERVICE)

    old = harness.stored("alert-1")
    assert (old.status, old.delivered_to) == (AlertStatus.PENDING_DRIVER, None)
    assert harness.event_of(1) == ("alert.registered", {"alert": alert_payload(old)})
    new = harness.stored("alert-2")
    assert (new.status, new.delivered_to) == (AlertStatus.DELIVERED, SESSION)
    assert harness.event_of(2) == ("alert.delivered", {"alert": alert_payload(new)})
    assert harness.logger.named("alert.undelivered") == [
        {"alert_id": "alert-1", "session_id": SESSION, "reason": "SERVICE_CHANGED"}
    ]


@pytest.mark.spec("driver_demand.AC-02")
def test_choosing_the_same_departure_keeps_the_requests_delivered(harness: Harness) -> None:
    harness.add(alert_at(1))

    harness.deliver(session_of(1, service=SERVICE), SERVICE)

    assert harness.stored("alert-1").status is AlertStatus.DELIVERED
    assert harness.logger.named("alert.undelivered") == []


@pytest.mark.spec("driver_demand.AC-02")
def test_a_session_without_a_departure_delivers_nothing(harness: Harness) -> None:
    harness.add(_pending(1))

    harness.deliver(session_of(1), None)

    assert harness.events.published == []


@pytest.mark.spec("driver_demand.AC-03")
def test_closing_a_shift_returns_its_requests_to_pending(harness: Harness) -> None:
    harness.add(alert_at(1), alert_at(2), alert_at(3, delivered_to="session-2"))

    harness.undeliver(SESSION)

    for number in (1, 2):
        alert = harness.stored(f"alert-{number}")
        assert (alert.status, alert.delivered_to) == (AlertStatus.PENDING_DRIVER, None)
        assert harness.event_of(number) == ("alert.registered", {"alert": alert_payload(alert)})
    assert harness.stored("alert-3").delivered_to == "session-2"
    assert [f["reason"] for f in harness.logger.named("alert.undelivered")] == [
        "SESSION_CLOSED",
        "SESSION_CLOSED",
    ]


@pytest.mark.spec("driver_demand.AC-12")
def test_delivery_logs_only_the_alert_and_the_shift(harness: Harness) -> None:
    harness.add(_pending(1, needs=(Need.RAMP, Need.SEAT)))

    harness.deliver(session_of(1, service=SERVICE), None)
    harness.undeliver(SESSION, reason=UndeliveryReason.SERVICE_CHANGED)

    assert harness.logger.events == [
        ("alert.delivered", {"alert_id": "alert-1", "session_id": SESSION}),
        (
            "alert.undelivered",
            {"alert_id": "alert-1", "session_id": SESSION, "reason": "SERVICE_CHANGED"},
        ),
    ]
    logged = repr(harness.logger.events)
    assert "device" not in logged
    assert "RAMP" not in logged


@dataclass
class ObservedHarness:
    inner: FakeAlertRepository = field(default_factory=FakeAlertRepository)
    logger: RecordingLogger = field(default_factory=RecordingLogger)
    delivered: list[str] = field(default_factory=list)

    @property
    def repository(self) -> DeliveryObservingAlerts:
        return DeliveryObservingAlerts(self.inner, self.delivered.append, self.logger)


@pytest.mark.spec("driver_demand.AC-01")
def test_storing_a_delivered_request_notifies_its_shift() -> None:
    harness = ObservedHarness()

    stored = harness.repository.add(alert_at(1, needs=(Need.SEAT,)))

    assert stored.alert_id == "alert-1"
    assert harness.inner.get("alert-1") == stored
    assert harness.delivered == [SESSION]


@pytest.mark.spec("driver_demand.AC-12")
def test_a_request_delivered_on_creation_logs_only_the_alert_and_the_shift() -> None:
    harness = ObservedHarness()

    harness.repository.add(alert_at(1, needs=(Need.SEAT,)))

    assert harness.logger.events == [
        ("alert.delivered", {"alert_id": "alert-1", "session_id": SESSION})
    ]


@pytest.mark.spec("driver_demand.AC-01")
def test_a_request_without_a_driver_notifies_nobody() -> None:
    harness = ObservedHarness()

    harness.repository.add(_pending(1))

    assert harness.delivered == []
    assert harness.logger.events == []


@pytest.mark.spec("driver_demand.AC-01")
def test_a_request_that_lost_the_race_notifies_nobody() -> None:
    harness = ObservedHarness()
    winner = alert_at(2, stop_id="s1")
    harness.inner.race = winner

    stored = harness.repository.add(replace(alert_at(1, stop_id="s1"), device_hash="device-2"))

    assert stored.alert_id == "alert-2"
    assert harness.delivered == []


def test_the_observed_repository_is_the_inner_one_for_everything_else() -> None:
    inner = FakeAlertRepository()
    harness = ObservedHarness(inner=inner)
    repository: AlertRepository = harness.repository
    alert = alert_at(1)
    repository.add(alert)

    assert repository.find_active(alert.device_hash, alert.stop_id, alert.line) == alert
    assert repository.list_by_device(alert.device_hash) == [alert]
    assert repository.get("alert-1") == alert
    assert repository.list_all() == [alert]
    assert repository.list_by_session(SESSION) == [alert]
    assert repository.list_by_trip(TRIP, MONDAY) == [alert]
    repository.update_tracking("alert-1", alert.tracking)
    repository.set_delivery("alert-1", AlertStatus.PENDING_DRIVER, None)
    assert inner.alerts["alert-1"].status is AlertStatus.PENDING_DRIVER
    assert repository.delete("alert-1") is True


@pytest.mark.spec("driver_demand.AC-01")
def test_the_directory_finds_the_open_shift_of_the_trip() -> None:
    directory = SessionDriverDirectory(InMemorySessions(session_of(1, service=SERVICE)))

    assert directory.find_driver("93", 0, TRIP, MONDAY) == DriverRef(SESSION)


@pytest.mark.spec("driver_demand.AC-01")
def test_the_directory_finds_nobody_for_a_trip_without_a_shift() -> None:
    directory = SessionDriverDirectory(InMemorySessions(session_of(1, service=SERVICE)))

    assert directory.find_driver("93", 0, "trip-2", MONDAY) is None
    assert directory.find_driver("93", 0, TRIP, MONDAY + timedelta(days=1)) is None
