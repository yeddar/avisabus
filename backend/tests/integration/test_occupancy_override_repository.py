"""`SqliteOccupancyOverrideRepository` over a temporary database (occupancy_sensor T-05)."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, text

from avisabus.adapters.outbound.persistence.db import create_engine
from avisabus.adapters.outbound.persistence.sqlite_occupancy_override import (
    SqliteOccupancyOverrideRepository,
)
from avisabus.config import Settings
from avisabus.domain.models.occupancy import OccupancyLevel
from avisabus.domain.ports.occupancy import OccupancyOverride, OccupancyOverrideRepository

NOW = datetime(2026, 11, 2, 7, 30, tzinfo=UTC)


def _override(line: str, level: OccupancyLevel, minutes: float) -> OccupancyOverride:
    return OccupancyOverride(line, level, NOW + timedelta(minutes=minutes))


@pytest.fixture
def repo(engine: Engine) -> SqliteOccupancyOverrideRepository:
    return SqliteOccupancyOverrideRepository(engine)


def test_repository_satisfies_the_port(repo: SqliteOccupancyOverrideRepository) -> None:
    port: OccupancyOverrideRepository = repo
    assert port.active(NOW) == []


def test_init_db_creates_the_override_table(engine: Engine) -> None:
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(occupancy_override)")).fetchall()
    assert [(c.name, c.type, bool(c.notnull), bool(c.pk)) for c in columns] == [
        ("line", "TEXT", True, True),
        ("level", "TEXT", True, False),
        ("expires_at", "TEXT", True, False),
    ]


@pytest.mark.spec("occupancy_sensor.AC-11")
def test_set_stores_level_and_expiry_in_utc_iso_8601(
    repo: SqliteOccupancyOverrideRepository, engine: Engine
) -> None:
    madrid_time = timezone(timedelta(hours=1))
    expires = datetime(2026, 11, 2, 9, 0, tzinfo=madrid_time)  # 08:00 UTC
    repo.set(OccupancyOverride("93", OccupancyLevel.FULL, expires))
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT line, level, expires_at FROM occupancy_override")).all()
    assert [tuple(r) for r in rows] == [("93", "FULL", "2026-11-02T08:00:00+00:00")]
    [stored] = repo.active(NOW)
    assert stored == OccupancyOverride("93", OccupancyLevel.FULL, expires)
    assert stored.expires_at.tzinfo == UTC


@pytest.mark.spec("occupancy_sensor.AC-11")
def test_set_replaces_the_override_of_the_same_line(
    repo: SqliteOccupancyOverrideRepository,
) -> None:
    repo.set(_override("93", OccupancyLevel.FULL, 30))
    repo.set(_override("93", OccupancyLevel.FREE, 10))
    assert repo.active(NOW) == [_override("93", OccupancyLevel.FREE, 10)]


@pytest.mark.spec("occupancy_sensor.AC-12")
def test_active_excludes_expired_overrides(repo: SqliteOccupancyOverrideRepository) -> None:
    repo.set(_override("93", OccupancyLevel.FULL, 30))
    repo.set(_override("70", OccupancyLevel.MEDIUM, 0.5))
    assert [o.line for o in repo.active(NOW)] == ["70", "93"]
    assert [o.line for o in repo.active(NOW + timedelta(seconds=29, microseconds=999_999))] == [
        "70",
        "93",
    ]
    assert [o.line for o in repo.active(NOW + timedelta(seconds=30))] == ["93"]
    assert repo.active(NOW + timedelta(minutes=30)) == []


@pytest.mark.spec("occupancy_sensor.AC-12")
def test_clear_removes_only_that_line(repo: SqliteOccupancyOverrideRepository) -> None:
    repo.set(_override("93", OccupancyLevel.FULL, 30))
    repo.set(_override("70", OccupancyLevel.FREE, 30))
    assert repo.clear("93") is True
    assert repo.clear("93") is False
    assert repo.active(NOW) == [_override("70", OccupancyLevel.FREE, 30)]


@pytest.mark.spec("occupancy_sensor.AC-14")
def test_overrides_are_shared_between_engines_of_the_same_database(
    repo: SqliteOccupancyOverrideRepository, db_settings: Settings
) -> None:
    other_process = create_engine(db_settings)
    try:
        SqliteOccupancyOverrideRepository(other_process).set(
            _override("93", OccupancyLevel.FULL, 30)
        )
        assert repo.active(NOW) == [_override("93", OccupancyLevel.FULL, 30)]
    finally:
        other_process.dispose()
