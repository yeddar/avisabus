"""`SqliteDriverCodeRepository` over a temporary database (driver_codes_cli T-02)."""

import traceback
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_driver_codes import SqliteDriverCodeRepository
from avisabus.config import Settings
from avisabus.domain.errors import DriverCodeCollisionError
from avisabus.domain.models.driver import DriverCode
from avisabus.domain.ports.driver import DriverCodeRepository

NOW = datetime(2026, 11, 9, 15, 40, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def _code(code_id: str = "dc-aaaaaa", code_hash: str = HASH_A, minutes: int = 0) -> DriverCode:
    return DriverCode(code_id, code_hash, "Tablet 3", NOW + timedelta(minutes=minutes), None)


@pytest.fixture
def repo(engine: Engine) -> SqliteDriverCodeRepository:
    return SqliteDriverCodeRepository(engine)


def test_repository_satisfies_the_port(repo: SqliteDriverCodeRepository) -> None:
    port: DriverCodeRepository = repo
    assert port.list_all() == []


def test_init_db_creates_the_driver_code_table(engine: Engine) -> None:
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(driver_code)")).fetchall()
    assert [(c.name, c.type, bool(c.notnull), bool(c.pk)) for c in columns] == [
        ("code_id", "TEXT", True, True),
        ("code_hash", "TEXT", True, False),
        ("label", "TEXT", True, False),
        ("created_at", "TEXT", False, False),
        ("revoked_at", "TEXT", False, False),
    ]


def test_init_db_adds_the_table_to_an_existing_database(db_settings: Settings) -> None:
    engine = create_engine(db_settings)
    try:
        init_db(engine)
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE driver_code"))
        init_db(engine)
        assert SqliteDriverCodeRepository(engine).list_all() == []
    finally:
        engine.dispose()


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_add_then_get_and_find_by_hash(repo: SqliteDriverCodeRepository) -> None:
    code = _code()
    repo.add(code)
    assert repo.get("dc-aaaaaa") == code
    assert repo.find_by_hash(HASH_A) == code


def test_get_and_find_by_hash_of_unknown_values(repo: SqliteDriverCodeRepository) -> None:
    assert repo.get("dc-nope00") is None
    assert repo.find_by_hash(HASH_B) is None


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_only_the_hash_is_written_to_the_table(
    repo: SqliteDriverCodeRepository, engine: Engine
) -> None:
    repo.add(_code())
    with engine.connect() as conn:
        row = conn.execute(text("SELECT * FROM driver_code")).mappings().one()
    assert set(row) == {"code_id", "code_hash", "label", "created_at", "revoked_at"}
    assert row["code_hash"] == HASH_A


def test_dates_are_stored_in_utc_iso_8601(repo: SqliteDriverCodeRepository, engine: Engine) -> None:
    madrid_time = timezone(timedelta(hours=1))
    code = DriverCode(
        "dc-aaaaaa", HASH_A, "T", datetime(2026, 11, 9, 16, 40, tzinfo=madrid_time), None
    )
    repo.add(code)
    with engine.connect() as conn:
        stored = conn.execute(text("SELECT created_at FROM driver_code")).scalar_one()
    assert stored == "2026-11-09T15:40:00+00:00"
    loaded = repo.get("dc-aaaaaa")
    assert loaded is not None
    assert loaded.created_at == code.created_at
    assert loaded.created_at.tzinfo == UTC


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_add_rejects_an_existing_hash(repo: SqliteDriverCodeRepository) -> None:
    repo.add(_code())
    with pytest.raises(DriverCodeCollisionError):
        repo.add(_code("dc-bbbbbb", HASH_A))
    assert [code.code_id for code in repo.list_all()] == ["dc-aaaaaa"]


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_add_rejects_the_hash_of_a_revoked_code(repo: SqliteDriverCodeRepository) -> None:
    repo.add(_code())
    repo.revoke("dc-aaaaaa", NOW)
    with pytest.raises(DriverCodeCollisionError):
        repo.add(_code("dc-bbbbbb", HASH_A))


@pytest.mark.spec("driver_codes_cli.AC-01")
def test_add_rejects_an_existing_code_id(repo: SqliteDriverCodeRepository) -> None:
    repo.add(_code())
    with pytest.raises(DriverCodeCollisionError):
        repo.add(_code("dc-aaaaaa", HASH_B))


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_collision_error_carries_no_stored_values(repo: SqliteDriverCodeRepository) -> None:
    repo.add(_code())
    with pytest.raises(DriverCodeCollisionError) as error:
        repo.add(_code("dc-bbbbbb", HASH_A))
    assert HASH_A not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True


@pytest.mark.spec("driver_codes_cli.AC-03")
def test_a_failed_write_exposes_neither_the_hash_nor_the_label(
    repo: SqliteDriverCodeRepository, engine: Engine
) -> None:
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE driver_code"))  # the INSERT fails with OperationalError
    with pytest.raises(OperationalError) as error:
        repo.add(_code())
    shown = "".join(traceback.format_exception(error.value))
    assert "driver_code" in shown  # the error itself is still reported
    assert HASH_A not in shown
    assert "Tablet 3" not in shown


def test_list_all_is_ordered_by_creation(repo: SqliteDriverCodeRepository) -> None:
    repo.add(_code("dc-cccccc", HASH_A, minutes=10))
    repo.add(_code("dc-bbbbbb", HASH_B, minutes=-10))
    repo.add(_code("dc-aaaaaa", "c" * 64, minutes=0))
    assert [code.code_id for code in repo.list_all()] == ["dc-bbbbbb", "dc-aaaaaa", "dc-cccccc"]


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_stores_the_date_and_returns_the_code(repo: SqliteDriverCodeRepository) -> None:
    repo.add(_code())
    at = NOW + timedelta(hours=1)
    revoked = repo.revoke("dc-aaaaaa", at)
    assert revoked is not None
    assert revoked.revoked_at == at
    assert revoked.revoked is True
    assert repo.get("dc-aaaaaa") == revoked


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_of_an_unknown_code_returns_none(repo: SqliteDriverCodeRepository) -> None:
    assert repo.revoke("dc-nope00", NOW) is None


@pytest.mark.spec("driver_codes_cli.AC-05")
def test_revoke_keeps_the_original_date(repo: SqliteDriverCodeRepository) -> None:
    repo.add(_code())
    repo.revoke("dc-aaaaaa", NOW)
    again = repo.revoke("dc-aaaaaa", NOW + timedelta(hours=1))
    assert again is not None
    assert again.revoked_at == NOW
