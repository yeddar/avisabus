"""`avisabus occupancy override …` with a temporary database and a FakeClock (T-05).

`gtfs_mini` is imported once per module into a template database that every test copies, so
line 93 and its trips exist. The sensor is built over its own engine, as the API process would.
"""

import asyncio
import csv
import shutil
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine
from typer.testing import CliRunner, Result

from avisabus.adapters.inbound.cli import occupancy as occupancy_cli
from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.inbound.cli.main import app
from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.adapters.outbound.occupancy.simulated_sensor import SimulatedOccupancySensor
from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_network import (
    SqliteGtfsFeedWriter,
    SqliteNetworkRepository,
)
from avisabus.adapters.outbound.persistence.sqlite_occupancy_override import (
    SqliteOccupancyOverrideRepository,
)
from avisabus.application.import_gtfs_feed import ImportGtfsFeed, ImportGtfsFeedCommand
from avisabus.config import ConfigurationError, Settings
from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyThresholds,
    VehicleRef,
)
from avisabus.domain.ports.clock import Clock
from avisabus.domain.services.occupancy_classifier import classify_occupancy
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.occupancy import InMemoryOccupancyOverrideRepository

runner = CliRunner()
NOW = datetime(2026, 11, 2, 7, 30, tzinfo=UTC)  # Monday, 08:30 in Madrid
SERVICE_DATE = date(2026, 11, 2)


def _csv(name: str) -> list[dict[str, str]]:
    with (GTFS_MINI / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


ROUTE_LINES = {row["route_id"]: row["route_short_name"] for row in _csv("routes.txt")}
TRIPS_BY_LINE: dict[str, list[str]] = {}
for _row in _csv("trips.txt"):
    TRIPS_BY_LINE.setdefault(ROUTE_LINES[_row["route_id"]], []).append(_row["trip_id"])
LINE_93_TRIPS = TRIPS_BY_LINE["93"][:25]
LINE_70_TRIPS = TRIPS_BY_LINE["70"][:25]


def _settings(path: Path) -> Settings:
    return Settings(_env_file=None, env="test", database_url=f"sqlite:///{path}")  # type: ignore[call-arg]


@pytest.fixture(scope="module")
def template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("occupancy") / "template.sqlite"
    engine = create_engine(_settings(path))
    init_db(engine)
    use_case = ImportGtfsFeed(CsvGtfsFeedReader, SqliteGtfsFeedWriter(engine), FakeClock(NOW))
    asyncio.run(use_case.execute(ImportGtfsFeedCommand(GTFS_MINI)))
    engine.dispose()
    return path


@pytest.fixture
def db_settings(tmp_path: Path, template_db: Path) -> Settings:
    path = tmp_path / "avisabus.sqlite"
    shutil.copyfile(template_db, path)
    return _settings(path)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture(autouse=True)
def _container(
    monkeypatch: pytest.MonkeyPatch, db_settings: Settings, clock: FakeClock
) -> Iterator[None]:
    """The CLI builds its dependencies with the test settings and the fake clock."""

    def build(_settings: Settings, _clock: Clock) -> CliContainer:
        return build_cli_container(db_settings, clock)

    monkeypatch.setattr(occupancy_cli, "build_cli_container", build)
    monkeypatch.setattr(occupancy_cli, "configure_logging", lambda _level: None)
    # The CLI builds `Settings()`: with a secret, stop_tokens_qr does not log its dev-secret
    # warning, which would otherwise be printed before the `--list` output.
    monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", "x" * 32)
    yield


@pytest.fixture
def api_engine(db_settings: Settings) -> Iterator[Engine]:
    """Engine of the API process, separate from the ones the CLI opens."""
    engine = create_engine(db_settings)
    yield engine
    engine.dispose()


@pytest.fixture
def sensor(api_engine: Engine, clock: FakeClock) -> SimulatedOccupancySensor:
    return SimulatedOccupancySensor(
        network=SqliteNetworkRepository(api_engine),
        overrides=SqliteOccupancyOverrideRepository(api_engine),
        clock=clock,
        capacity=90,
        seats=28,
        seed="avisabus",
    )


def _run(*args: str) -> Result:
    return runner.invoke(app, ["occupancy", "override", *args], prog_name="avisabus")


def _read(sensor: SimulatedOccupancySensor, trip_id: str, at: datetime) -> OccupancyReading:
    """Sync read: the tests are sync because the CLI runs its own event loop."""
    reading = asyncio.run(sensor.read(VehicleRef(trip_id, SERVICE_DATE), at))
    assert reading is not None
    return reading


def _level(reading: OccupancyReading) -> OccupancyLevel:
    return classify_occupancy(reading, OccupancyThresholds()).level


def _simulated(api_engine: Engine, trip_ids: list[str], at: datetime) -> list[int]:
    """Readings of a sensor without overrides (fresh in-memory repository)."""
    plain = SimulatedOccupancySensor(
        network=SqliteNetworkRepository(api_engine),
        overrides=InMemoryOccupancyOverrideRepository(),
        clock=FakeClock(NOW),
        capacity=90,
        seats=28,
        seed="avisabus",
    )
    return [(_read(plain, t, at)).occupied for t in trip_ids]


# --- AC-11: set an override ---


@pytest.mark.spec("occupancy_sensor.AC-11")
@pytest.mark.parametrize("level", list(OccupancyLevel))
def test_override_forces_the_level_of_every_trip_of_the_line(
    sensor: SimulatedOccupancySensor, level: OccupancyLevel
) -> None:
    result = _run("--line", "93", "--level", level.value, "--minutes", "30")
    assert result.exit_code == 0, result.output
    assert f"línea 93 → {level.value} hasta 2026-11-02 08:00 UTC" in result.output
    for at in (NOW, NOW + timedelta(minutes=29, seconds=59)):
        for trip_id in LINE_93_TRIPS:
            assert _level(_read(sensor, trip_id, at)) is level


@pytest.mark.spec("occupancy_sensor.AC-11")
def test_override_leaves_the_other_lines_simulated(
    sensor: SimulatedOccupancySensor, api_engine: Engine
) -> None:
    assert _run("--line", "93", "--level", "FULL").exit_code == 0
    got = [(_read(sensor, t, NOW)).occupied for t in LINE_70_TRIPS]
    assert got == _simulated(api_engine, LINE_70_TRIPS, NOW)


@pytest.mark.spec("occupancy_sensor.AC-11")
def test_override_lasts_thirty_minutes_by_default(api_engine: Engine) -> None:
    result = _run("--line", "93", "--level", "MEDIUM")
    assert result.exit_code == 0, result.output
    [override] = SqliteOccupancyOverrideRepository(api_engine).active(NOW)
    assert override.expires_at == NOW + timedelta(minutes=30)
    assert override.level is OccupancyLevel.MEDIUM


@pytest.mark.spec("occupancy_sensor.AC-11")
def test_level_is_case_insensitive(api_engine: Engine) -> None:
    assert _run("--line", "93", "--level", "full", "--minutes", "5").exit_code == 0
    [override] = SqliteOccupancyOverrideRepository(api_engine).active(NOW)
    assert override.level is OccupancyLevel.FULL


def test_unknown_line_exits_2_and_stores_nothing(api_engine: Engine) -> None:
    result = _run("--line", "999", "--level", "FULL")
    assert result.exit_code == 2
    assert "ERROR: la línea 999 no existe en la red activa" in result.output
    assert SqliteOccupancyOverrideRepository(api_engine).active(NOW) == []


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--line", "93"),  # neither --level, --clear nor --list
        ("--level", "FULL"),  # no --line
        ("--line", "93", "--level", "EMPTY"),
        ("--line", "93", "--level", "FULL", "--minutes", "0"),
        ("--line", "93", "--level", "FULL", "--clear"),
        ("--line", "93", "--clear", "--minutes", "5"),
        ("--list", "--line", "93"),
        ("--list", "--clear"),
    ],
)
def test_invalid_option_combinations_exit_2(api_engine: Engine, args: tuple[str, ...]) -> None:
    result = _run(*args)
    assert result.exit_code == 2, result.output
    assert SqliteOccupancyOverrideRepository(api_engine).active(NOW) == []


def test_invalid_configuration_prevents_the_cli_from_starting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AVISABUS_OCCUPANCY_SEATS", "91")
    result = _run("--list")
    assert isinstance(result.exception, ConfigurationError)
    assert result.exit_code != 0


# --- AC-12: expiry and --clear ---


@pytest.mark.spec("occupancy_sensor.AC-12")
def test_sensor_returns_to_simulation_when_the_override_expires(
    sensor: SimulatedOccupancySensor, api_engine: Engine, clock: FakeClock
) -> None:
    assert _run("--line", "93", "--level", "FREE", "--minutes", "10").exit_code == 0
    assert [(_read(sensor, t, NOW)).occupied for t in LINE_93_TRIPS] == [18] * len(LINE_93_TRIPS)
    clock.advance(timedelta(minutes=10))
    got = [(_read(sensor, t, NOW)).occupied for t in LINE_93_TRIPS]
    assert got == _simulated(api_engine, LINE_93_TRIPS, NOW)


@pytest.mark.spec("occupancy_sensor.AC-12")
def test_clear_returns_the_line_to_simulation(
    sensor: SimulatedOccupancySensor, api_engine: Engine, clock: FakeClock
) -> None:
    assert _run("--line", "93", "--level", "FULL").exit_code == 0
    assert _run("--line", "70", "--level", "FREE").exit_code == 0
    assert {_level(_read(sensor, t, NOW)) for t in LINE_93_TRIPS} == {OccupancyLevel.FULL}
    result = _run("--line", "93", "--clear")
    assert result.exit_code == 0, result.output
    assert "Forzado eliminado para la línea 93" in result.output
    clock.advance(timedelta(seconds=5))
    got = [(_read(sensor, t, NOW)).occupied for t in LINE_93_TRIPS]
    assert got == _simulated(api_engine, LINE_93_TRIPS, NOW)
    assert {(_read(sensor, t, NOW)).occupied for t in LINE_70_TRIPS} == {18}


@pytest.mark.spec("occupancy_sensor.AC-12")
def test_clear_of_a_line_without_override_says_so() -> None:
    result = _run("--line", "93", "--clear")
    assert result.exit_code == 0
    assert "La línea 93 no tenía ningún forzado activo" in result.output


@pytest.mark.spec("occupancy_sensor.AC-12")
def test_clear_of_an_unknown_line_exits_2() -> None:
    result = _run("--line", "999", "--clear")
    assert result.exit_code == 2
    assert "ERROR: la línea 999 no existe en la red activa" in result.output


# --- AC-13: --list ---


@pytest.mark.spec("occupancy_sensor.AC-13")
def test_list_shows_the_active_overrides_with_their_expiry(clock: FakeClock) -> None:
    assert _run("--line", "C2", "--level", "FULL", "--minutes", "45").exit_code == 0
    assert _run("--line", "93", "--level", "MEDIUM", "--minutes", "30").exit_code == 0
    assert _run("--line", "70", "--level", "FREE", "--minutes", "5").exit_code == 0
    result = _run("--list")
    assert result.exit_code == 0, result.output
    assert result.output.splitlines() == [
        "Forzados de ocupación activos:",
        "  Línea 70 · FREE · caduca 2026-11-02 07:35 UTC",
        "  Línea 93 · MEDIUM · caduca 2026-11-02 08:00 UTC",
        "  Línea C2 · FULL · caduca 2026-11-02 08:15 UTC",
    ]
    clock.advance(timedelta(minutes=5))
    later = _run("--list")
    assert "Línea 70" not in later.output
    assert "Línea 93 · MEDIUM · caduca 2026-11-02 08:00 UTC" in later.output


@pytest.mark.spec("occupancy_sensor.AC-13")
def test_list_without_active_overrides(clock: FakeClock) -> None:
    result = _run("--list")
    assert result.exit_code == 0
    assert result.output.strip() == "No hay forzados de ocupación activos."
    assert _run("--line", "93", "--level", "FULL", "--minutes", "1").exit_code == 0
    clock.advance(timedelta(minutes=1))
    assert _run("--list").output.strip() == "No hay forzados de ocupación activos."


# --- AC-14: changes from the CLI reach a running sensor within 5 s ---


@pytest.mark.spec("occupancy_sensor.AC-14")
def test_running_sensor_sees_cli_changes_within_five_seconds(
    sensor: SimulatedOccupancySensor, api_engine: Engine, clock: FakeClock
) -> None:
    trip_id = LINE_93_TRIPS[0]
    [simulated] = _simulated(api_engine, [trip_id], NOW)
    assert simulated != 86
    assert (_read(sensor, trip_id, NOW)).occupied == simulated  # caches "no overrides"
    clock.advance(timedelta(seconds=2))
    assert _run("--line", "93", "--level", "FULL").exit_code == 0
    clock.advance(timedelta(seconds=2, milliseconds=999))
    assert (_read(sensor, trip_id, NOW)).occupied == simulated  # 4.999 s: cached
    clock.advance(timedelta(milliseconds=1))
    assert (_read(sensor, trip_id, NOW)).occupied == 86  # 5 s: refreshed
    assert _run("--line", "93", "--clear").exit_code == 0
    clock.advance(timedelta(seconds=5))
    assert (_read(sensor, trip_id, NOW)).occupied == simulated


@pytest.mark.spec("occupancy_sensor.AC-11")
def test_override_survives_a_gtfs_reimport(db_settings: Settings, api_engine: Engine) -> None:
    assert _run("--line", "93", "--level", "FULL").exit_code == 0
    use_case = ImportGtfsFeed(CsvGtfsFeedReader, SqliteGtfsFeedWriter(api_engine), FakeClock(NOW))
    asyncio.run(use_case.execute(ImportGtfsFeedCommand(GTFS_MINI)))
    assert "Línea 93 · FULL" in _run("--list").output
