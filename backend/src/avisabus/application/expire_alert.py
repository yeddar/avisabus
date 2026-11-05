"""Effects of the expiry of a stop request (alert_expiry design §3, AC-08, RF-28).

The alert is deleted with its needs (RNF-06), the device's sockets get `alert.expired` with the
reason and, if it had been delivered, the driver view is refreshed. An alert that no longer
exists (cancelled, or expired by the other task, in between) has nothing to announce.

Privacy: the log carries neither the device hash nor the needs.
"""

from typing import Any, Protocol

from avisabus.domain.models.alert import Alert, AlertStatus, ExpiryReason
from avisabus.domain.models.events import Event
from avisabus.domain.ports.alerts import AlertRepository, DriverViewNotifier
from avisabus.domain.ports.events import EventPublisher, device_channel

ALERT_EXPIRED = "alert.expired"
"""Event of the device channel (`{"type": "alert.expired", "alert_id": …, "reason": …}`) and
log event."""


class Logger(Protocol):
    def info(self, event: str, **fields: Any) -> Any: ...


class ExpireAlert:
    def __init__(
        self,
        alerts: AlertRepository,
        events: EventPublisher,
        drivers: DriverViewNotifier,
        logger: Logger,
    ) -> None:
        self._alerts = alerts
        self._events = events
        self._drivers = drivers
        self._log = logger

    def __call__(self, alert: Alert, reason: ExpiryReason) -> bool:
        """False, without any effect, if the alert no longer existed."""
        if not self._alerts.delete(alert.alert_id):
            return False
        self._events.publish(
            device_channel(alert.device_hash),
            Event(ALERT_EXPIRED, {"alert_id": alert.alert_id, "reason": reason.value}),
        )
        if alert.status is AlertStatus.DELIVERED and alert.delivered_to is not None:
            self._drivers.alert_removed(alert.delivered_to)
        self._log.info(
            ALERT_EXPIRED,
            alert_id=alert.alert_id,
            stop_id=alert.stop_id,
            line=alert.line,
            reason=reason.value,
        )
        return True
