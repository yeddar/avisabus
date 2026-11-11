"""Fakes of the alert ports for the unit tests (never in production)."""

from dataclasses import dataclass, field, replace
from datetime import date, datetime
from typing import Any

from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking
from avisabus.domain.models.events import Event
from avisabus.domain.ports.alerts import DriverRef


@dataclass
class FakeAlertRepository:
    """In memory, with the unique (device_hash, stop_id, line) of the SQLite one. `race` is an
    alert that another request stores right before the next `add`."""

    alerts: dict[str, Alert] = field(default_factory=dict)
    race: Alert | None = None

    def add(self, alert: Alert) -> Alert:
        if self.race is not None:
            self.alerts[self.race.alert_id] = self.race
            self.race = None
        existing = self.find_active(alert.device_hash, alert.stop_id, alert.line)
        if existing is not None:
            return existing
        self.alerts[alert.alert_id] = alert
        return alert

    def find_active(self, device_hash: str, stop_id: str, line: str) -> Alert | None:
        return next(
            (
                a
                for a in self.alerts.values()
                if (a.device_hash, a.stop_id, a.line) == (device_hash, stop_id, line)
            ),
            None,
        )

    def list_by_device(self, device_hash: str) -> list[Alert]:
        return sorted(
            (a for a in self.alerts.values() if a.device_hash == device_hash),
            key=lambda a: (a.created_at, a.alert_id),
        )

    def get(self, alert_id: str) -> Alert | None:
        return self.alerts.get(alert_id)

    def list_all(self) -> list[Alert]:
        return sorted(self.alerts.values(), key=lambda a: (a.created_at, a.alert_id))

    def list_by_session(self, session_id: str) -> list[Alert]:
        return sorted(
            (a for a in self.alerts.values() if a.delivered_to == session_id),
            key=lambda a: (a.created_at, a.alert_id),
        )

    def list_by_trip(self, trip_id: str, service_date: date) -> list[Alert]:
        return sorted(
            (
                a
                for a in self.alerts.values()
                if (a.trip_id, a.service_date) == (trip_id, service_date)
            ),
            key=lambda a: (a.created_at, a.alert_id),
        )

    def set_delivery(self, alert_id: str, status: AlertStatus, delivered_to: str | None) -> None:
        if alert_id in self.alerts:
            self.alerts[alert_id] = replace(
                self.alerts[alert_id], status=status, delivered_to=delivered_to
            )

    def update_tracking(self, alert_id: str, tracking: AlertTracking) -> None:
        """Like the SQLite one: nothing happens if the alert no longer exists."""
        if alert_id in self.alerts:
            self.alerts[alert_id] = replace(self.alerts[alert_id], tracking=tracking)

    def delete(self, alert_id: str) -> bool:
        return self.alerts.pop(alert_id, None) is not None


@dataclass
class FakeDriverDirectory:
    driver: DriverRef | None = None
    queries: list[tuple[str, int, str, date]] = field(default_factory=list)

    def find_driver(
        self, line: str, direction_id: int, trip_id: str, service_date: date
    ) -> DriverRef | None:
        self.queries.append((line, direction_id, trip_id, service_date))
        return self.driver


@dataclass
class RecordingPublisher:
    published: list[tuple[str, Event]] = field(default_factory=list)

    def publish(self, channel: str, event: Event) -> None:
        self.published.append((channel, event))

    def subscribe(self, channel: str) -> Any:
        raise NotImplementedError

    def subscriber_count(self, channel: str | None = None) -> int:
        return 0


@dataclass
class RecordingLimiter:
    """Admits until `retry_after` is set; keeps the attempts of each key."""

    retry_after: int | None = None
    attempts: dict[str, list[datetime]] = field(default_factory=dict)

    def acquire(self, key: str, now: datetime) -> int | None:
        self.attempts.setdefault(key, []).append(now)
        return self.retry_after

    def release(self, key: str, now: datetime) -> None:
        self.attempts[key].pop()

    def count(self, key: str) -> int:
        return len(self.attempts.get(key, []))


@dataclass
class RecordingLogger:
    events: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def debug(self, event: str, **fields: Any) -> None:
        self.events.append(("debug", event, fields))

    def info(self, event: str, **fields: Any) -> None:
        self.events.append(("info", event, fields))

    def warning(self, event: str, **fields: Any) -> None:
        self.events.append(("warning", event, fields))

    def error(self, event: str, **fields: Any) -> None:
        self.events.append(("error", event, fields))

    def named(self, event: str) -> list[dict[str, Any]]:
        return [fields for _, name, fields in self.events if name == event]
