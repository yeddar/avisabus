"""SQLite `DriverSessionRepository` and its table (driver_session design §4).

Dates are stored as UTC ISO-8601 text. The table is not versioned by feed, so it has its own
metadata; `init_db` creates it with `create_all` (ADR-011). Only the SHA-256 of the token and the
last position are kept, and both disappear with the row (RNF-06).
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    Column,
    Engine,
    Float,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
    delete,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.exc import IntegrityError

from avisabus.domain.errors import DepartureTakenError
from avisabus.domain.models.driver import DriverPosition, DriverService, DriverSession

driver_session_metadata = MetaData()

driver_session = Table(
    "driver_session",
    driver_session_metadata,
    Column("session_id", Text, primary_key=True),
    Column("token_hash", Text, unique=True, nullable=False),
    Column("code_id", Text, unique=True, nullable=False),
    Column("started_at", Text, nullable=False),
    Column("line", Text, nullable=True),
    Column("direction_id", Integer, nullable=True),
    Column("trip_id", Text, nullable=True),
    Column("service_date", Text, nullable=True),
    Column("lat", Float, nullable=True),
    Column("lon", Float, nullable=True),
    Column("accuracy_m", Float, nullable=True),
    Column("recorded_at", Text, nullable=True),
    Column("last_fix_at", Text, nullable=True),
    Column("last_seen_at", Text, nullable=True),
    Column("progress_m", Float, nullable=True),
    Column("off_route", Integer, nullable=False),
    Column("progress_recorded_at", Text, nullable=True),
    Index(
        "ux_driver_session_departure",
        "trip_id",
        "service_date",
        unique=True,
        sqlite_where=text("trip_id IS NOT NULL"),
    ),
)


class SqliteDriverSessionRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, session: DriverSession) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                insert(driver_session).values(
                    session_id=session.session_id,
                    token_hash=session.token_hash,
                    code_id=session.code_id,
                    started_at=_to_text(session.started_at),
                    **_mutable_values(session),
                )
            )

    def by_token_hash(self, token_hash: str) -> DriverSession | None:
        return self._first(select(driver_session).where(driver_session.c.token_hash == token_hash))

    def by_code(self, code_id: str) -> DriverSession | None:
        return self._first(select(driver_session).where(driver_session.c.code_id == code_id))

    def by_trip(self, trip_id: str, service_date: date) -> DriverSession | None:
        return self._first(
            select(driver_session).where(
                driver_session.c.trip_id == trip_id,
                driver_session.c.service_date == service_date.isoformat(),
            )
        )

    def list_all(self) -> list[DriverSession]:
        statement = select(driver_session).order_by(
            driver_session.c.started_at, driver_session.c.session_id
        )
        with self._engine.connect() as conn:
            return [_to_model(row) for row in conn.execute(statement)]

    def save(self, session: DriverSession) -> None:
        try:
            with self._engine.begin() as conn:
                conn.execute(
                    update(driver_session)
                    .where(driver_session.c.session_id == session.session_id)
                    .values(**_mutable_values(session))
                )
        except IntegrityError:
            # The partial unique index is the only constraint an update can break.
            raise DepartureTakenError() from None

    def delete(self, session_id: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                delete(driver_session).where(driver_session.c.session_id == session_id)
            )
        return result.rowcount > 0

    def _first(self, statement: Any) -> DriverSession | None:
        with self._engine.connect() as conn:
            row = conn.execute(statement).first()
        return None if row is None else _to_model(row)


def _mutable_values(session: DriverSession) -> dict[str, Any]:
    service, position = session.service, session.position
    return {
        "line": None if service is None else service.line,
        "direction_id": None if service is None else service.direction_id,
        "trip_id": None if service is None else service.trip_id,
        "service_date": None if service is None else service.service_date.isoformat(),
        "lat": None if position is None else position.lat,
        "lon": None if position is None else position.lon,
        "accuracy_m": None if position is None else position.accuracy_m,
        "recorded_at": None if position is None else _to_text(position.recorded_at),
        "last_fix_at": _optional_text(session.last_fix_at),
        "last_seen_at": _optional_text(session.last_seen_at),
        "progress_m": session.progress_m,
        "off_route": int(session.off_route),
        "progress_recorded_at": _optional_text(session.progress_recorded_at),
    }


def _to_model(row: Any) -> DriverSession:
    service = None
    if row.trip_id is not None:
        service = DriverService(
            line=row.line,
            direction_id=row.direction_id,
            trip_id=row.trip_id,
            service_date=date.fromisoformat(row.service_date),
        )
    position = None
    if row.recorded_at is not None:
        position = DriverPosition(
            lat=row.lat,
            lon=row.lon,
            accuracy_m=row.accuracy_m,
            recorded_at=_from_text(row.recorded_at),
        )
    return DriverSession(
        session_id=row.session_id,
        token_hash=row.token_hash,
        code_id=row.code_id,
        started_at=_from_text(row.started_at),
        service=service,
        position=position,
        progress_m=row.progress_m,
        off_route=bool(row.off_route),
        last_fix_at=_optional_datetime(row.last_fix_at),
        last_seen_at=_optional_datetime(row.last_seen_at),
        progress_recorded_at=_optional_datetime(row.progress_recorded_at),
    )


def _optional_text(value: datetime | None) -> str | None:
    return None if value is None else _to_text(value)


def _optional_datetime(value: str | None) -> datetime | None:
    return None if value is None else _from_text(value)


def _to_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _from_text(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
