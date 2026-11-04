"""Ports of the stop requests (alert_create design §3)."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol

from avisabus.domain.models.alert import Alert, AlertTracking


class AlertRepository(Protocol):
    """Active alerts. Every stored alert is active: expired and cancelled ones are deleted."""

    def add(self, alert: Alert) -> Alert:
        """Store `alert`, unless the device already has an active one at that stop and line: then
        return that one, unchanged (unique index, AC-07)."""
        ...

    def find_active(self, device_hash: str, stop_id: str, line: str) -> Alert | None: ...

    def list_by_device(self, device_hash: str) -> list[Alert]:
        """Alerts of the device in every stop, by `created_at`."""
        ...

    def get(self, alert_id: str) -> Alert | None: ...

    def list_all(self) -> list[Alert]:
        """Used by `alert_expiry`."""
        ...

    def update_tracking(self, alert_id: str, tracking: AlertTracking) -> None: ...

    def delete(self, alert_id: str) -> bool:
        """True if it existed."""
        ...


@dataclass(frozen=True, slots=True)
class DriverRef:
    session_id: str


class DriverDirectory(Protocol):
    def find_driver(
        self, line: str, direction_id: int, trip_id: str, service_date: date
    ) -> DriverRef | None:
        """Driver session of that bus; `None` when nobody drives it (always in block 3)."""
        ...


class DriverViewNotifier(Protocol):
    def alert_removed(self, session_id: str) -> None:
        """Implemented by `driver_demand` (block 4)."""
        ...


class RateLimiter(Protocol):
    def acquire(self, key: str, now: datetime) -> int | None:
        """Record the attempt; return `None` if it is admitted, else the seconds of
        `Retry-After`."""
        ...

    def release(self, key: str, now: datetime) -> None:
        """Undo the last attempt (AC-07: a `200` does not count)."""
        ...
