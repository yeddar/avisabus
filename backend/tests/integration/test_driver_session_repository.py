"""`SqliteDriverSessionRepository` over a temporary database (driver_session T-01)."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, text

from avisabus.adapters.outbound.persistence.sqlite_driver_sessions import (
    SqliteDriverSessionRepository,
)
from avisabus.domain.errors import DepartureTakenError
from avisabus.domain.models.driver import DriverPosition, DriverService, DriverSession
from avisabus.domain.ports.driver import DriverSessionRepository

NOW = datetime(2026, 11, 9, 15, 40, tzinfo=UTC)
SERVICE = DriverService("93", 0, "trip-1", date(2026, 11, 9))
POSITION = DriverPosition(39.47, -0.37, 8.5, NOW - timedelta(seconds=5))


def _session(number: int = 1, service: DriverService | None = None) -> DriverSession:
    return DriverSession(
        session_id=f"session-{number}",
        token_hash=f"{number:064d}",
        code_id=f"dc-{number:06d}",
        started_at=NOW,
        service=service,
        position=None,
        progress_m=None,
        off_route=False,
        last_position_at=None,
    )


@pytest.fixture
def repo(engine: Engine) -> SqliteDriverSessionRepository:
    return SqliteDriverSessionRepository(engine)


def test_repository_satisfies_the_port(repo: SqliteDriverSessionRepository) -> None:
    port: DriverSessionRepository = repo
    assert port.list_all() == []


def test_table_has_the_columns_of_the_design(engine: Engine) -> None:
    with engine.connect() as conn:
        columns = [row.name for row in conn.execute(text("PRAGMA table_info(driver_session)"))]
    assert columns == [
        "session_id",
        "token_hash",
        "code_id",
        "started_at",
        "line",
        "direction_id",
        "trip_id",
        "service_date",
        "lat",
        "lon",
        "accuracy_m",
        "recorded_at",
        "last_position_at",
        "progress_m",
        "off_route",
        "progress_recorded_at",
    ]


def test_new_session_round_trips_without_service_nor_position(
    repo: SqliteDriverSessionRepository,
) -> None:
    session = _session()
    repo.add(session)
    assert repo.by_token_hash(session.token_hash) == session
    assert repo.by_code(session.code_id) == session


def test_saved_service_position_and_progress_round_trip(
    repo: SqliteDriverSessionRepository,
) -> None:
    session = _session()
    repo.add(session)
    updated = replace(
        session,
        service=SERVICE,
        position=POSITION,
        progress_m=1234.5,
        off_route=True,
        last_position_at=NOW,
        progress_recorded_at=NOW - timedelta(seconds=1),
    )
    repo.save(updated)
    assert repo.by_token_hash(session.token_hash) == updated
    assert repo.by_trip(SERVICE.trip_id, SERVICE.service_date) == updated


def test_dates_are_normalised_to_utc(repo: SqliteDriverSessionRepository) -> None:
    madrid = timezone(timedelta(hours=1))
    session = replace(_session(), started_at=NOW.astimezone(madrid))
    repo.add(session)
    found = repo.by_code(session.code_id)
    assert found is not None
    assert found.started_at == NOW
    assert found.started_at.utcoffset() == timedelta(0)


def test_lookups_of_unknown_values_find_nothing(repo: SqliteDriverSessionRepository) -> None:
    repo.add(_session())
    assert repo.by_token_hash("nope") is None
    assert repo.by_code("dc-nope00") is None
    assert repo.by_trip("trip-1", date(2026, 11, 9)) is None


def test_by_trip_distinguishes_the_service_day(repo: SqliteDriverSessionRepository) -> None:
    repo.add(_session(service=SERVICE))
    assert repo.by_trip("trip-1", SERVICE.service_date) is not None
    assert repo.by_trip("trip-1", date(2026, 11, 10)) is None


def test_list_all_returns_every_open_session(repo: SqliteDriverSessionRepository) -> None:
    repo.add(_session(1))
    repo.add(_session(2))
    assert {session.session_id for session in repo.list_all()} == {"session-1", "session-2"}


def test_delete_removes_the_session_with_its_position(
    repo: SqliteDriverSessionRepository, engine: Engine
) -> None:
    session = replace(_session(), position=POSITION, last_position_at=NOW)
    repo.add(session)
    assert repo.delete(session.session_id) is True
    assert repo.list_all() == []
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM driver_session")).scalar() == 0


def test_delete_of_an_unknown_session_is_false(repo: SqliteDriverSessionRepository) -> None:
    assert repo.delete("session-9") is False


def test_two_sessions_cannot_hold_the_same_departure(
    repo: SqliteDriverSessionRepository,
) -> None:
    repo.add(_session(1, service=SERVICE))
    other = _session(2)
    repo.add(other)
    with pytest.raises(DepartureTakenError):
        repo.save(replace(other, service=SERVICE))


def test_the_same_trip_on_another_day_is_not_the_same_departure(
    repo: SqliteDriverSessionRepository,
) -> None:
    repo.add(_session(1, service=SERVICE))
    repo.add(_session(2, service=replace(SERVICE, service_date=date(2026, 11, 10))))
    assert len(repo.list_all()) == 2


def test_sessions_without_service_do_not_collide(repo: SqliteDriverSessionRepository) -> None:
    repo.add(_session(1))
    repo.add(_session(2))
    assert all(session.service is None for session in repo.list_all())


def test_repr_hides_the_token_hash_and_the_position() -> None:
    text_of_session = repr(replace(_session(), position=POSITION))
    assert "token_hash" not in text_of_session
    assert "39.47" not in text_of_session
