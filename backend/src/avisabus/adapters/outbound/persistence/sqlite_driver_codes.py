"""SQLite `DriverCodeRepository` and its table (driver_codes_cli design §3).

Dates are stored as UTC ISO-8601 text. The table is not versioned by feed, so it has its own
metadata; `init_db` creates it with `create_all` (ADR-011).
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Column, Engine, MetaData, Table, Text, insert, select, update
from sqlalchemy.exc import IntegrityError

from avisabus.domain.errors import DriverCodeCollisionError
from avisabus.domain.models.driver import DriverCode

driver_code_metadata = MetaData()

driver_code = Table(
    "driver_code",
    driver_code_metadata,
    Column("code_id", Text, primary_key=True),
    Column("code_hash", Text, unique=True, nullable=False),
    Column("label", Text, nullable=False),
    Column("created_at", Text),
    Column("revoked_at", Text, nullable=True),
)


class SqliteDriverCodeRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add(self, code: DriverCode) -> None:
        values = {
            "code_id": code.code_id,
            "code_hash": code.code_hash,
            "label": code.label,
            "created_at": _to_text(code.created_at),
            "revoked_at": None if code.revoked_at is None else _to_text(code.revoked_at),
        }
        try:
            with self._engine.begin() as conn:
                conn.execute(insert(driver_code).values(values))
        except IntegrityError:
            # `from None`: SQLAlchemy's message includes the statement parameters.
            raise DriverCodeCollisionError() from None

    def get(self, code_id: str) -> DriverCode | None:
        return self._first(select(driver_code).where(driver_code.c.code_id == code_id))

    def find_by_hash(self, code_hash: str) -> DriverCode | None:
        return self._first(select(driver_code).where(driver_code.c.code_hash == code_hash))

    def list_all(self) -> list[DriverCode]:
        statement = select(driver_code).order_by(driver_code.c.created_at, driver_code.c.code_id)
        with self._engine.connect() as conn:
            return [_to_model(row) for row in conn.execute(statement)]

    def revoke(self, code_id: str, at: datetime) -> DriverCode | None:
        with self._engine.begin() as conn:
            conn.execute(
                update(driver_code)
                .where(driver_code.c.code_id == code_id, driver_code.c.revoked_at.is_(None))
                .values(revoked_at=_to_text(at))
            )
            row = conn.execute(select(driver_code).where(driver_code.c.code_id == code_id)).first()
        return None if row is None else _to_model(row)

    def _first(self, statement: Any) -> DriverCode | None:
        with self._engine.connect() as conn:
            row = conn.execute(statement).first()
        return None if row is None else _to_model(row)


def _to_model(row: Any) -> DriverCode:
    return DriverCode(
        code_id=row.code_id,
        code_hash=row.code_hash,
        label=row.label,
        created_at=_from_text(row.created_at),
        revoked_at=None if row.revoked_at is None else _from_text(row.revoked_at),
    )


def _to_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _from_text(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)
