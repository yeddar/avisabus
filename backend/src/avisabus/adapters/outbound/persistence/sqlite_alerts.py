"""SQLite `AlertRepository` and the `alert` table (alert_create design §4).

Every row is an active alert: expired and cancelled ones are deleted (RNF-06). The device is only
kept as its `device_hash`, never as the `X-Device-Id` in clear, and the needs only inside the
alert (AC-12). Datetimes are UTC ISO-8601 text; `needs` is the canonical list joined by commas
(`""` without needs). The table has its own metadata, created by `init_db` (ADR-011).
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Engine,
    Index,
    Integer,
    MetaData,
    Row,
    Table,
    Text,
    UniqueConstraint,
    delete,
    select,
    update,
)
from sqlalchemy.dialects.sqlite import insert

from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking, Need

alert_metadata = MetaData()

alert_table = Table(
    "alert",
    alert_metadata,
    Column("alert_id", Text, primary_key=True),
    Column("device_hash", Text, nullable=False),
    Column("stop_id", Text, nullable=False),
    Column("stop_name", Text, nullable=False),
    Column("line", Text, nullable=False),
    Column("direction_id", Integer, nullable=False),
    Column("destination", Text, nullable=False),
    Column("trip_id", Text, nullable=False),
    Column("service_date", Text, nullable=False),
    Column("stop_sequence", Integer, nullable=False),
    Column("needs", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("delivered_to", Text, nullable=True),
    Column("created_at", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
    Column("last_seen_at", Text, nullable=True),
    Column("last_arrival_at", Text, nullable=False),
    Column("last_delay_s", Integer, nullable=False),
    # One active alert per device, stop and line (AC-07, RF-19).
    UniqueConstraint("device_hash", "stop_id", "line", name="uq_alert_device_stop_line"),
    Index("ix_alert_stop_id", "stop_id"),
)


class SqliteAlertRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, alert: Alert) -> Alert:
        """Insert unless the device already has an alert at that stop and line; in a race the
        unique index decides, and the loser gets the winner's alert (AC-07)."""
        statement = (
            insert(alert_table)
            .values(_row(alert))
            .on_conflict_do_nothing(
                index_elements=[
                    alert_table.c.device_hash,
                    alert_table.c.stop_id,
                    alert_table.c.line,
                ]
            )
        )
        with self._engine.begin() as conn:
            inserted = conn.execute(statement).rowcount > 0
            if inserted:
                return alert
            existing = conn.execute(
                select(alert_table).where(*_key(alert.device_hash, alert.stop_id, alert.line))
            ).one()
        return _alert(existing)

    def find_active(self, device_hash: str, stop_id: str, line: str) -> Alert | None:
        return self._one(select(alert_table).where(*_key(device_hash, stop_id, line)))

    def list_by_device(self, device_hash: str) -> list[Alert]:
        return self._all(select(alert_table).where(alert_table.c.device_hash == device_hash))

    def get(self, alert_id: str) -> Alert | None:
        return self._one(select(alert_table).where(alert_table.c.alert_id == alert_id))

    def list_all(self) -> list[Alert]:
        return self._all(select(alert_table))

    def update_tracking(self, alert_id: str, tracking: AlertTracking) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                update(alert_table)
                .where(alert_table.c.alert_id == alert_id)
                .values(_tracking_row(tracking))
            )

    def delete(self, alert_id: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(delete(alert_table).where(alert_table.c.alert_id == alert_id))
        return result.rowcount > 0

    def _one(self, statement: Any) -> Alert | None:
        with self._engine.connect() as conn:
            row = conn.execute(statement).first()
        return None if row is None else _alert(row)

    def _all(self, statement: Any) -> list[Alert]:
        """By `created_at` (compared as datetimes, not as ISO text), then `alert_id`."""
        with self._engine.connect() as conn:
            alerts = [_alert(row) for row in conn.execute(statement)]
        return sorted(alerts, key=lambda alert: (alert.created_at, alert.alert_id))


def _key(device_hash: str, stop_id: str, line: str) -> tuple[Any, ...]:
    return (
        alert_table.c.device_hash == device_hash,
        alert_table.c.stop_id == stop_id,
        alert_table.c.line == line,
    )


def _row(alert: Alert) -> dict[str, Any]:
    return {
        "alert_id": alert.alert_id,
        "device_hash": alert.device_hash,
        "stop_id": alert.stop_id,
        "stop_name": alert.stop_name,
        "line": alert.line,
        "direction_id": alert.direction_id,
        "destination": alert.destination,
        "trip_id": alert.trip_id,
        "service_date": alert.service_date.isoformat(),
        "stop_sequence": alert.stop_sequence,
        "needs": ",".join(need.value for need in alert.needs),
        "status": alert.status.value,
        "delivered_to": alert.delivered_to,
        "created_at": _text(alert.created_at),
        "expires_at": _text(alert.expires_at),
        **_tracking_row(alert.tracking),
    }


def _tracking_row(tracking: AlertTracking) -> dict[str, Any]:
    return {
        "last_seen_at": None if tracking.last_seen_at is None else _text(tracking.last_seen_at),
        "last_arrival_at": _text(tracking.last_arrival_at),
        "last_delay_s": tracking.last_delay_s,
    }


def _alert(row: Row[Any]) -> Alert:
    return Alert(
        alert_id=row.alert_id,
        device_hash=row.device_hash,
        stop_id=row.stop_id,
        stop_name=row.stop_name,
        line=row.line,
        direction_id=row.direction_id,
        destination=row.destination,
        trip_id=row.trip_id,
        service_date=date.fromisoformat(row.service_date),
        stop_sequence=row.stop_sequence,
        needs=tuple(Need(value) for value in row.needs.split(",") if value),
        status=AlertStatus(row.status),
        delivered_to=row.delivered_to,
        created_at=_datetime(row.created_at),
        expires_at=_datetime(row.expires_at),
        tracking=AlertTracking(
            last_seen_at=None if row.last_seen_at is None else _datetime(row.last_seen_at),
            last_arrival_at=_datetime(row.last_arrival_at),
            last_delay_s=row.last_delay_s,
        ),
    )


def _text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _datetime(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
