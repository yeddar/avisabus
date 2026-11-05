"""`SqliteAlertRepository` over a temporary database (alert_create T-03)."""

import threading
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine, text

from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_alerts import SqliteAlertRepository
from avisabus.config import Settings
from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking, Need
from avisabus.domain.ports.alerts import AlertRepository

NOW = datetime(2026, 11, 4, 7, 40, tzinfo=UTC)
HASH_A = "a" * 64
HASH_B = "b" * 64


def _alert(
    alert_id: str = "6f1c0d6e-0000-4000-8000-000000000001",
    device_hash: str = HASH_A,
    stop_id: str = "508",
    line: str = "93",
    created_at: datetime = NOW,
    needs: tuple[Need, ...] = (Need.RAMP, Need.VISUAL),
) -> Alert:
    return Alert(
        alert_id=alert_id,
        device_hash=device_hash,
        stop_id=stop_id,
        stop_name="Parc de l'Oest - Enguera",
        line=line,
        direction_id=0,
        destination="Passeig Marítim - Hospital Malva-rosa",
        trip_id="93_994_561_488_2271_2_122",
        service_date=date(2026, 11, 4),
        stop_sequence=17,
        needs=needs,
        status=AlertStatus.PENDING_DRIVER,
        delivered_to=None,
        created_at=created_at,
        expires_at=created_at + timedelta(minutes=30),
        tracking=AlertTracking(
            last_seen_at=None, last_arrival_at=created_at + timedelta(minutes=7), last_delay_s=-92
        ),
    )


@pytest.fixture
def repo(engine: Engine) -> SqliteAlertRepository:
    return SqliteAlertRepository(engine)


def test_repository_satisfies_the_port(repo: SqliteAlertRepository) -> None:
    port: AlertRepository = repo
    assert port.list_all() == []


@pytest.mark.spec("alert_create.AC-12")
def test_init_db_creates_the_alert_table_without_the_device_id(engine: Engine) -> None:
    with engine.connect() as conn:
        columns = conn.execute(text("PRAGMA table_info(alert)")).fetchall()
        indexes = conn.execute(text("PRAGMA index_list(alert)")).fetchall()
        unique = [
            [c.name for c in conn.execute(text(f"PRAGMA index_info('{index.name}')"))]
            for index in indexes
            if index.unique and index.origin == "u"
        ]
        by_stop = [
            [c.name for c in conn.execute(text(f"PRAGMA index_info('{index.name}')"))]
            for index in indexes
            if not index.unique
        ]
    assert [(c.name, c.type, bool(c.notnull), bool(c.pk)) for c in columns] == [
        ("alert_id", "TEXT", True, True),
        ("device_hash", "TEXT", True, False),
        ("stop_id", "TEXT", True, False),
        ("stop_name", "TEXT", True, False),
        ("line", "TEXT", True, False),
        ("direction_id", "INTEGER", True, False),
        ("destination", "TEXT", True, False),
        ("trip_id", "TEXT", True, False),
        ("service_date", "TEXT", True, False),
        ("stop_sequence", "INTEGER", True, False),
        ("needs", "TEXT", True, False),
        ("status", "TEXT", True, False),
        ("delivered_to", "TEXT", False, False),
        ("created_at", "TEXT", True, False),
        ("expires_at", "TEXT", True, False),
        ("last_seen_at", "TEXT", False, False),
        ("last_arrival_at", "TEXT", True, False),
        ("last_delay_s", "INTEGER", True, False),
    ]
    assert unique == [["device_hash", "stop_id", "line"]]
    assert by_stop == [["stop_id"]]
    assert "device_id" not in {c.name for c in columns}


@pytest.mark.spec("alert_create.AC-12")
def test_alerts_survive_a_restart_with_the_same_database(db_settings: Settings) -> None:
    first = create_engine(db_settings)
    init_db(first)
    stored = _alert()
    SqliteAlertRepository(first).add(stored)
    first.dispose()

    second = create_engine(db_settings)
    init_db(second)  # idempotent: the table and its rows are kept
    try:
        assert SqliteAlertRepository(second).get(stored.alert_id) == stored
    finally:
        second.dispose()


@pytest.mark.spec("alert_create.AC-12")
def test_rows_hold_the_hash_and_the_needs_inside_the_alert(
    repo: SqliteAlertRepository, engine: Engine
) -> None:
    repo.add(_alert())
    repo.add(_alert("6f1c0d6e-0000-4000-8000-000000000002", line="70", needs=()))
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT device_hash, line, needs, service_date, created_at FROM alert")
        ).fetchall()
        tables = {row.name for row in conn.execute(text("SELECT name FROM sqlite_master"))}
    assert sorted(tuple(row) for row in rows) == [
        (HASH_A, "70", "", "2026-11-04", "2026-11-04T07:40:00+00:00"),
        (HASH_A, "93", "RAMP,VISUAL", "2026-11-04", "2026-11-04T07:40:00+00:00"),
    ]
    # No other table keeps the needs nor the device.
    assert not {name for name in tables if "need" in name or "device" in name}


def test_round_trip_of_every_field(repo: SqliteAlertRepository) -> None:
    alert = replace(
        _alert(needs=(Need.RAMP, Need.EXTRA_TIME, Need.SEAT, Need.VISUAL)),
        status=AlertStatus.DELIVERED,
        delivered_to="session-1",
        tracking=AlertTracking(
            last_seen_at=NOW + timedelta(seconds=20),
            last_arrival_at=NOW + timedelta(minutes=6, seconds=30),
            last_delay_s=45,
        ),
    )
    assert repo.add(alert) == alert
    assert repo.get(alert.alert_id) == alert
    assert repo.get("missing") is None


def test_datetimes_are_stored_in_utc(repo: SqliteAlertRepository) -> None:
    madrid = timezone(timedelta(hours=1))
    alert = _alert(created_at=NOW.astimezone(madrid))
    repo.add(alert)
    stored = repo.get(alert.alert_id)
    assert stored is not None
    assert stored.created_at == NOW
    assert stored.created_at.tzinfo == UTC


@pytest.mark.spec("alert_create.AC-07")
def test_add_returns_the_active_alert_of_the_device_at_that_stop_and_line(
    repo: SqliteAlertRepository,
) -> None:
    first = _alert()
    assert repo.add(first) == first
    second = replace(
        _alert("6f1c0d6e-0000-4000-8000-000000000002", needs=()),
        trip_id="another-bus",
    )
    assert repo.add(second) == first  # unchanged, nothing new
    assert repo.list_all() == [first]
    assert repo.find_active(HASH_A, "508", "93") == first
    assert repo.find_active(HASH_A, "508", "70") is None
    assert repo.find_active(HASH_B, "508", "93") is None


@pytest.mark.spec("alert_create.AC-07")
def test_other_devices_stops_and_lines_are_independent(repo: SqliteAlertRepository) -> None:
    alerts = [
        _alert("id-1"),
        _alert("id-2", device_hash=HASH_B),
        _alert("id-3", stop_id="2070"),
        _alert("id-4", line="70"),
    ]
    for alert in alerts:
        assert repo.add(alert) == alert
    assert len(repo.list_all()) == 4


@pytest.mark.spec("alert_create.AC-07")
def test_concurrent_adds_leave_a_single_alert(db_settings: Settings) -> None:
    engines = [create_engine(db_settings) for _ in range(2)]
    init_db(engines[0])
    repos = [SqliteAlertRepository(engine) for engine in engines]
    candidates = [_alert("id-1"), _alert("id-2")]
    barrier = threading.Barrier(2)
    results: list[Alert] = []

    def add(index: int) -> None:
        barrier.wait()
        results.append(repos[index].add(candidates[index]))

    threads = [threading.Thread(target=add, args=(index,)) for index in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    try:
        (stored,) = repos[0].list_all()
        assert stored in candidates
        assert results == [stored, stored]
    finally:
        for engine in engines:
            engine.dispose()


def test_list_by_device_in_every_stop_by_creation(repo: SqliteAlertRepository) -> None:
    later = _alert("id-1", created_at=NOW + timedelta(minutes=2))
    earlier = _alert("id-2", stop_id="2070", created_at=NOW)
    other = _alert("id-3", device_hash=HASH_B)
    for alert in (later, earlier, other):
        repo.add(alert)
    assert repo.list_by_device(HASH_A) == [earlier, later]
    assert repo.list_by_device(HASH_B) == [other]
    assert repo.list_by_device("c" * 64) == []
    assert repo.list_all() == [earlier, other, later]  # same instant: by alert_id


def test_update_tracking_and_delete(repo: SqliteAlertRepository) -> None:
    alert = _alert()
    repo.add(alert)
    tracking = AlertTracking(
        last_seen_at=NOW + timedelta(minutes=1),
        last_arrival_at=NOW + timedelta(minutes=8),
        last_delay_s=30,
    )
    repo.update_tracking(alert.alert_id, tracking)
    assert repo.get(alert.alert_id) == replace(alert, tracking=tracking)
    assert repo.delete(alert.alert_id) is True
    assert repo.delete(alert.alert_id) is False
    assert repo.get(alert.alert_id) is None
    # Once deleted, the device can request again at that stop and line.
    again = _alert("id-9")
    assert repo.add(again) == again


def test_in_memory_database() -> None:
    settings = Settings(_env_file=None, env="test", database_url="sqlite://")  # type: ignore[call-arg]
    engine = create_engine(settings)
    init_db(engine)
    repo = SqliteAlertRepository(engine)
    assert repo.add(_alert()) == _alert()
    engine.dispose()
