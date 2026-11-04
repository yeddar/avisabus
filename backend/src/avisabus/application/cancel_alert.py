"""Use case: a passenger cancels their stop request (alert_cancel design §3, CU-04).

Only the device that created the alert can cancel it; a missing, expired or foreign alert is the
same `AlertNotFoundError`, so the answer never reveals whether an `alert_id` exists for another
device (AC-02). The alert is deleted with its needs (RNF-06).

Privacy (AC-05): the log carries neither the device hash nor the needs.
"""

import hmac
from typing import Any, Protocol

from avisabus.domain.errors import AlertNotFoundError
from avisabus.domain.models.events import Event
from avisabus.domain.ports.alerts import AlertRepository, DriverViewNotifier
from avisabus.domain.ports.events import EventPublisher, device_channel

ALERT_CANCELLED = "alert.cancelled"
"""Event of the device channel and log event: `{"type": "alert.cancelled", "alert_id": …}`."""


class Logger(Protocol):
    def info(self, event: str, **fields: Any) -> Any: ...


class CancelAlert:
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

    async def execute(self, device_hash: str, alert_id: str) -> None:
        """Raises `AlertNotFoundError` (AC-02) without changing anything."""
        alert = self._alerts.get(alert_id)
        if alert is None or not hmac.compare_digest(alert.device_hash, device_hash):
            raise AlertNotFoundError()
        if not self._alerts.delete(alert_id):  # it expired in between
            raise AlertNotFoundError()

        self._events.publish(
            device_channel(device_hash), Event(ALERT_CANCELLED, {"alert_id": alert_id})
        )
        if alert.delivered_to is not None:
            self._drivers.alert_removed(alert.delivered_to)
        self._log.info(ALERT_CANCELLED, alert_id=alert_id, stop_id=alert.stop_id, line=alert.line)
