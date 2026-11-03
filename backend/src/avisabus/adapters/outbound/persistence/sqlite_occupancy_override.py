"""SQLite `OccupancyOverrideRepository` and its table (occupancy_sensor design §4).

`expires_at` is stored as UTC ISO-8601 text. The table is not versioned by feed, so it has its
own metadata (the network one only holds versioned tables); `init_db` creates both with
`create_all` (ADR-011).
"""

from datetime import UTC, datetime

from sqlalchemy import Column, Engine, MetaData, Table, Text, delete, select
from sqlalchemy.dialects.sqlite import insert

from avisabus.domain.models.occupancy import OccupancyLevel
from avisabus.domain.ports.occupancy import OccupancyOverride

occupancy_metadata = MetaData()

occupancy_override = Table(
    "occupancy_override",
    occupancy_metadata,
    Column("line", Text, primary_key=True),
    Column("level", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
)


class SqliteOccupancyOverrideRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def set(self, override: OccupancyOverride) -> None:
        values = {
            "line": override.line,
            "level": override.level.value,
            "expires_at": override.expires_at.astimezone(UTC).isoformat(),
        }
        statement = insert(occupancy_override).values(values)
        statement = statement.on_conflict_do_update(
            index_elements=[occupancy_override.c.line],
            set_={"level": statement.excluded.level, "expires_at": statement.excluded.expires_at},
        )
        with self._engine.begin() as conn:
            conn.execute(statement)

    def clear(self, line: str) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                delete(occupancy_override).where(occupancy_override.c.line == line)
            )
        return result.rowcount > 0

    def active(self, now: datetime) -> list[OccupancyOverride]:
        with self._engine.connect() as conn:
            rows = conn.execute(select(occupancy_override).order_by(occupancy_override.c.line))
            overrides = [
                OccupancyOverride(
                    line=row.line,
                    level=OccupancyLevel(row.level),
                    expires_at=datetime.fromisoformat(row.expires_at).astimezone(UTC),
                )
                for row in rows
            ]
        # Expiry is compared as datetimes, not as ISO text, so any precision compares right.
        return [override for override in overrides if override.expires_at > now]
