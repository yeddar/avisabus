"""Delivery of the stop requests to the shift that drives their bus (driver_demand design §3).

Every change stores the delivery, tells the passenger on their device channel and logs it. The
logs carry the `alert_id` and the `session_id`, never the needs nor the device (AC-12).
"""

from collections.abc import Callable
from dataclasses import replace
from datetime import date
from enum import StrEnum
from typing import Any, Protocol

from avisabus.application.alert_events import ALERT_DELIVERED, ALERT_REGISTERED, alert_event
from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking
from avisabus.domain.models.driver import DriverService, DriverSession
from avisabus.domain.ports.alerts import AlertRepository
from avisabus.domain.ports.events import EventPublisher, device_channel

ALERT_UNDELIVERED = "alert.undelivered"


class UndeliveryReason(StrEnum):
    SESSION_CLOSED = "SESSION_CLOSED"
    SERVICE_CHANGED = "SERVICE_CHANGED"


class Logger(Protocol):
    def info(self, event: str, **fields: Any) -> Any: ...


class UndeliverSessionAlerts:
    """Requests of a shift back to "no driver connected" (AC-02, AC-03, CU-10 3)."""

    def __init__(self, alerts: AlertRepository, events: EventPublisher, logger: Logger) -> None:
        self._alerts = alerts
        self._events = events
        self._log = logger

    def __call__(
        self, session_id: str, reason: UndeliveryReason = UndeliveryReason.SESSION_CLOSED
    ) -> None:
        for alert in self._alerts.list_by_session(session_id):
            self._alerts.set_delivery(alert.alert_id, AlertStatus.PENDING_DRIVER, None)
            pending = replace(alert, status=AlertStatus.PENDING_DRIVER, delivered_to=None)
            self._events.publish(
                device_channel(alert.device_hash), alert_event(ALERT_REGISTERED, pending)
            )
            self._log.info(
                ALERT_UNDELIVERED,
                alert_id=alert.alert_id,
                session_id=session_id,
                reason=reason.value,
            )


class DeliverPendingAlerts:
    """A shift chooses a departure: it takes the requests waiting for that bus (AC-02, CU-03 5a)
    and gives back the ones delivered through its previous departure."""

    def __init__(
        self,
        alerts: AlertRepository,
        events: EventPublisher,
        undeliver: UndeliverSessionAlerts,
        logger: Logger,
    ) -> None:
        self._alerts = alerts
        self._events = events
        self._undeliver = undeliver
        self._log = logger

    def __call__(self, session: DriverSession, previous: DriverService | None) -> None:
        service = session.service
        if service is None:
            return
        if previous is not None and previous != service:
            self._undeliver(session.session_id, reason=UndeliveryReason.SERVICE_CHANGED)
        for alert in self._alerts.list_by_trip(service.trip_id, service.service_date):
            if alert.status is AlertStatus.PENDING_DRIVER:
                self._deliver(alert, session.session_id)

    def _deliver(self, alert: Alert, session_id: str) -> None:
        self._alerts.set_delivery(alert.alert_id, AlertStatus.DELIVERED, session_id)
        delivered = replace(alert, status=AlertStatus.DELIVERED, delivered_to=session_id)
        self._events.publish(
            device_channel(alert.device_hash), alert_event(ALERT_DELIVERED, delivered)
        )
        self._log.info(ALERT_DELIVERED, alert_id=alert.alert_id, session_id=session_id)


class DeliveryObservingAlerts:
    """`AlertRepository` that notices a request stored already delivered (AC-01): `CreateAlert`
    decides the delivery and publishes `alert.delivered`, and this logs it and asks for a new view
    of the shift. Only an alert actually stored counts, not one that lost the race of AC-07."""

    def __init__(
        self,
        inner: AlertRepository,
        on_delivered: Callable[[str], None],
        logger: Logger,
    ) -> None:
        self._inner = inner
        self._on_delivered = on_delivered
        self._log = logger

    def add(self, alert: Alert) -> Alert:
        stored = self._inner.add(alert)
        if stored.alert_id == alert.alert_id and stored.delivered_to is not None:
            self._log.info(
                ALERT_DELIVERED, alert_id=stored.alert_id, session_id=stored.delivered_to
            )
            self._on_delivered(stored.delivered_to)
        return stored

    def find_active(self, device_hash: str, stop_id: str, line: str) -> Alert | None:
        return self._inner.find_active(device_hash, stop_id, line)

    def list_by_device(self, device_hash: str) -> list[Alert]:
        return self._inner.list_by_device(device_hash)

    def get(self, alert_id: str) -> Alert | None:
        return self._inner.get(alert_id)

    def list_all(self) -> list[Alert]:
        return self._inner.list_all()

    def list_by_session(self, session_id: str) -> list[Alert]:
        return self._inner.list_by_session(session_id)

    def list_by_trip(self, trip_id: str, service_date: date) -> list[Alert]:
        return self._inner.list_by_trip(trip_id, service_date)

    def set_delivery(self, alert_id: str, status: AlertStatus, delivered_to: str | None) -> None:
        self._inner.set_delivery(alert_id, status, delivered_to)

    def update_tracking(self, alert_id: str, tracking: AlertTracking) -> None:
        self._inner.update_tracking(alert_id, tracking)

    def delete(self, alert_id: str) -> bool:
        return self._inner.delete(alert_id)
