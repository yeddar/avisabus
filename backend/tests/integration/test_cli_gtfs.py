"""`avisabus gtfs import` / `avisabus gtfs info` with a temporary database and a FakeClock."""

import re
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from structlog.testing import capture_logs
from typer.testing import CliRunner, Result

from avisabus.adapters.inbound.cli import gtfs as gtfs_cli
from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.inbound.cli.main import app
from avisabus.config import Settings
from avisabus.domain.ports.clock import Clock
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import (
    GTFS_MINI,
    append_rows,
    copy_gtfs_mini,
    drop_column,
    read_rows,
    write_rows,
    zip_feed,
)

runner = CliRunner()
NORMAL_DAY = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)
COUNTS_LINE = "Líneas: 4 · Paradas: 178 · Viajes: 1 109 · Horarios de parada: 29 040"


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NORMAL_DAY)


@pytest.fixture(autouse=True)
def _container(
    monkeypatch: pytest.MonkeyPatch, db_settings: Settings, clock: FakeClock
) -> Iterator[None]:
    """The CLI builds its dependencies with the test settings and the fake clock."""

    def build(_settings: Settings, _clock: Clock) -> CliContainer:
        return build_cli_container(db_settings, clock)

    monkeypatch.setattr(gtfs_cli, "build_cli_container", build)
    monkeypatch.setattr(gtfs_cli, "configure_logging", lambda _level: None)
    yield


def _run(*args: str) -> Result:
    return runner.invoke(app, ["gtfs", *args], prog_name="avisabus")


def _active_version(result: Result) -> int:
    match = re.search(r"Versión activa: (\d+)", result.output)
    assert match is not None, result.output
    return int(match.group(1))


@pytest.mark.spec("gtfs_import.AC-01")
def test_import_directory_shows_counts_and_activates_the_feed() -> None:
    result = _run("import", str(GTFS_MINI))
    assert result.exit_code == 0, result.output
    assert "Feed importado (versión 1, feed_version 23-10-2026)" in result.output
    assert "Vigencia: 2026-10-16 → 2026-11-22" in result.output
    assert COUNTS_LINE in result.output
    assert "AVISO" not in result.output
    info = _run("info")
    assert info.exit_code == 0
    assert _active_version(info) == 1


@pytest.mark.spec("gtfs_import.AC-02")
def test_import_zip_works_like_a_directory(tmp_path: Path) -> None:
    archive = zip_feed(copy_gtfs_mini(tmp_path / "feed"), tmp_path / "gtfs.zip")
    result = _run("import", str(archive))
    assert result.exit_code == 0, result.output
    assert COUNTS_LINE in result.output


@pytest.mark.spec("gtfs_import.AC-03")
def test_missing_file_exits_2_and_keeps_previous_version(tmp_path: Path) -> None:
    assert _run("import", str(GTFS_MINI)).exit_code == 0
    feed = copy_gtfs_mini(tmp_path / "feed")
    (feed / "stops.txt").unlink()
    result = _run("import", str(feed))
    assert result.exit_code == 2
    assert "ERROR: falta stops.txt" in result.output
    info = _run("info")
    assert _active_version(info) == 1
    assert COUNTS_LINE in info.output


@pytest.mark.spec("gtfs_import.AC-03")
def test_missing_both_calendars_exits_2(tmp_path: Path) -> None:
    feed = copy_gtfs_mini(tmp_path / "feed")
    (feed / "calendar.txt").unlink()
    (feed / "calendar_dates.txt").unlink()
    result = _run("import", str(feed))
    assert result.exit_code == 2
    assert "ERROR: falta calendar.txt" in result.output


@pytest.mark.spec("gtfs_import.AC-04")
def test_missing_column_exits_2_naming_file_and_column(tmp_path: Path) -> None:
    assert _run("import", str(GTFS_MINI)).exit_code == 0
    feed = copy_gtfs_mini(tmp_path / "feed")
    drop_column(feed / "stop_times.txt", "departure_time")
    result = _run("import", str(feed))
    assert result.exit_code == 2
    assert "ERROR: falta la columna departure_time en stop_times.txt" in result.output
    assert _active_version(_run("info")) == 1


@pytest.mark.spec("gtfs_import.AC-05")
def test_invalid_value_exits_2_and_keeps_previous_version(tmp_path: Path) -> None:
    assert _run("import", str(GTFS_MINI)).exit_code == 0
    feed = copy_gtfs_mini(tmp_path / "feed")
    rows = read_rows(feed / "stop_times.txt")
    rows[20000][1] = "25:99:00"
    write_rows(feed / "stop_times.txt", rows)
    result = _run("import", str(feed))
    assert result.exit_code == 2
    assert "stop_times.txt" in result.output
    assert "línea 20001" in result.output
    info = _run("info")
    assert _active_version(info) == 1
    assert COUNTS_LINE in info.output


def test_unknown_path_exits_2(tmp_path: Path) -> None:
    result = _run("import", str(tmp_path / "missing"))
    assert result.exit_code == 2
    assert "ERROR" in result.output


def test_unexpected_error_exits_2_without_its_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    feed = copy_gtfs_mini(tmp_path / "feed")
    rows = read_rows(feed / "stops.txt")
    write_rows(feed / "stops.txt", [*rows, rows[1]])  # duplicated stop_id -> IntegrityError
    result = _run("import", str(feed))
    assert result.exit_code == 2
    assert "IntegrityError" in result.output
    assert "UNIQUE" not in result.output
    assert _run("info").exit_code == 1


@pytest.mark.spec("gtfs_import.AC-28")
def test_import_summary_counts_ignored_route_ids(tmp_path: Path) -> None:
    feed = copy_gtfs_mini(tmp_path / "feed")
    header = read_rows(feed / "routes.txt")[0]
    values = {"route_id": "1033", "agency_id": "EMT", "route_short_name": "23", "route_type": "3"}
    append_rows(feed / "routes.txt", [[values.get(column, "") for column in header]])
    result = _run("import", str(feed))
    assert result.exit_code == 0, result.output
    assert "route_id sin viajes ignorados: 1" in result.output
    assert "Líneas: 4 ·" in result.output


@pytest.mark.spec("gtfs_import.AC-18")
def test_info_shows_version_import_date_validity_and_counts(clock: FakeClock) -> None:
    assert _run("import", str(GTFS_MINI)).exit_code == 0
    clock.set(datetime(2026, 11, 2, 9, 0, tzinfo=UTC))
    result = _run("info")
    assert result.exit_code == 0
    assert "Versión activa: 1 (feed_version 23-10-2026)" in result.output
    assert "Importado: 2026-10-31 08:00 UTC" in result.output
    assert "Vigencia: 2026-10-16 → 2026-11-22" in result.output
    assert COUNTS_LINE in result.output
    assert "route_id sin viajes ignorados: 0" in result.output


@pytest.mark.spec("gtfs_import.AC-18")
def test_info_without_feed_exits_1() -> None:
    result = _run("info")
    assert result.exit_code == 1
    assert "No hay ningún feed importado" in result.output


@pytest.mark.spec("gtfs_import.AC-06")
def test_reimport_replaces_the_active_version() -> None:
    assert _run("import", str(GTFS_MINI)).exit_code == 0
    result = _run("import", str(GTFS_MINI))
    assert "Feed importado (versión 2," in result.output
    assert _active_version(_run("info")) == 2


def _logged(events: list[dict[str, object]], name: str) -> list[dict[str, object]]:
    return [e for e in events if e["event"] == name]


@pytest.mark.spec("gtfs_import.AC-19")
@pytest.mark.parametrize("command", [("import", str(GTFS_MINI)), ("info",)])
def test_feed_expiring_within_7_days_warns_and_logs(
    clock: FakeClock, command: tuple[str, ...]
) -> None:
    if command[0] == "info":
        assert _run("import", str(GTFS_MINI)).exit_code == 0
    clock.set(datetime(2026, 11, 17, 10, 0, tzinfo=UTC))
    with capture_logs() as events:
        result = _run(*command)
    assert result.exit_code == 0
    assert "AVISO: el feed caduca en 5 días (2026-11-22)" in result.output
    (event,) = _logged(events, "gtfs.feed_expiring")
    assert event["days_left"] == 5
    assert event["log_level"] == "warning"


@pytest.mark.spec("gtfs_import.AC-19")
@pytest.mark.parametrize("command", [("import", str(GTFS_MINI)), ("info",)])
def test_expired_feed_warns_and_logs(clock: FakeClock, command: tuple[str, ...]) -> None:
    if command[0] == "info":
        assert _run("import", str(GTFS_MINI)).exit_code == 0
    clock.set(datetime(2026, 11, 25, 10, 0, tzinfo=UTC))
    with capture_logs() as events:
        result = _run(*command)
    assert result.exit_code == 0
    assert "AVISO: el feed caducó el 2026-11-22 (hace 3 días)" in result.output
    (event,) = _logged(events, "gtfs.feed_expired")
    assert event["days_ago"] == 3


@pytest.mark.spec("gtfs_import.AC-19")
def test_valid_feed_does_not_warn(clock: FakeClock) -> None:
    clock.set(datetime(2026, 11, 14, 10, 0, tzinfo=UTC))  # 8 days left
    with capture_logs() as events:
        result = _run("import", str(GTFS_MINI))
    assert "AVISO" not in result.output
    assert not [e for e in events if str(e["event"]).startswith("gtfs.feed_")]


@pytest.mark.spec("gtfs_import.AC-26")
def test_info_directions_lists_origin_ends_headsigns_and_patterns() -> None:
    assert _run("import", str(GTFS_MINI)).exit_code == 0
    result = _run("info", "--directions")
    assert result.exit_code == 0
    out = result.output
    blocks = re.findall(r"^Línea (\S+) · sentido (\d) · origen: (\w+)", out, flags=re.M)
    assert blocks == [
        (line, str(d), "derived") for line in ("70", "93", "98", "C2") for d in (0, 1)
    ]
    assert "Línea 98 · sentido 0 · origen: derived · viajes: 106 · patrones: 2" in out
    assert "Patrón principal 1054_487_2229: 487 Cid - Pere Maria Orts → 2229" in out
    assert "Headsigns: Estació del Cabanyal (71); Passeig Marítim - Hospital Malva-rosa (35)" in out
    assert "Patrones: 1054_487_2229 (71); 1055_487_2271 (35)" in out


def test_info_without_directions_flag_has_no_direction_list() -> None:
    assert _run("import", str(GTFS_MINI)).exit_code == 0
    assert "Línea 70 · sentido" not in _run("info").output


def test_gtfs_group_shows_help() -> None:
    result = _run("--help")
    assert result.exit_code == 0
    assert "import" in result.output
    assert "info" in result.output
