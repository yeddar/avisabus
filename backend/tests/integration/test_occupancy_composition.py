"""The occupancy sensor and classifier are composed with the configured values (occupancy_sensor
AC-15, T-09).

`avisabus.main` builds everything at import time, so it is imported in a subprocess with a
temporary working directory and a copy of a database with `gtfs_mini` and some demo overrides:
the tests never touch `data/` nor a developer `.env`. The configuration is deliberately far from
the defaults (capacity, seats, seed and both thresholds) so that a value left at its default in
the composition changes the readings.

The expected readings are computed here with a `SimulatedOccupancySensor` built from the
configured values (and a fake clock), independently of `main.py`.
"""

import asyncio
import csv
import dataclasses
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from avisabus.adapters.inbound.cli.container import CliContainer
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
from avisabus.config import Settings
from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyThresholds,
    VehicleRef,
)
from avisabus.domain.ports.occupancy import OccupancyOverride, OccupancySensor
from avisabus.domain.services.occupancy_classifier import classify_occupancy, override_occupied
from avisabus.domain.services.occupancy_simulation import service_day_start
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.occupancy import InMemoryOccupancyOverrideRepository
from tests.support.sae import E01

NOW = datetime(2026, 11, 2, 7, 30, tzinfo=UTC)  # Monday, 08:30 in Madrid
SERVICE_DATE = date(2026, 11, 2)
NEVER_EXPIRES = datetime(2100, 1, 1, tzinfo=UTC)

CAPACITY = 60
SEATS = 20
SEED = "composition-test"
THRESHOLDS = OccupancyThresholds(medium=0.30, full=0.70)
DEFAULT_THRESHOLDS = OccupancyThresholds()
CONFIGURED = {
    "AVISABUS_OCCUPANCY_CAPACITY": str(CAPACITY),
    "AVISABUS_OCCUPANCY_SEATS": str(SEATS),
    "AVISABUS_OCCUPANCY_SEED": SEED,
    "AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM": str(THRESHOLDS.medium),
    "AVISABUS_OCCUPANCY_THRESHOLD_FULL": str(THRESHOLDS.full),
}
FORCED = {"93": OccupancyLevel.FULL, "70": OccupancyLevel.FREE, "C2": OccupancyLevel.MEDIUM}
SIMULATED_LINE = "98"  # no override: plain simulation (seed, capacity)

PROBE = """
import asyncio, json, sys
from datetime import date, datetime
import avisabus.main as main
from avisabus.domain.models.occupancy import VehicleRef

async def read_all(queries):
    readings = {}
    for trip_id, service_date, at in queries:
        vehicle = VehicleRef(trip_id, date.fromisoformat(service_date))
        reading = await main.occupancy_sensor.read(vehicle, datetime.fromisoformat(at))
        readings[trip_id] = [reading.capacity, reading.seats, reading.occupied]
    return readings

queries = json.loads(sys.argv[1])
thresholds = main.occupancy_thresholds
print(json.dumps({
    "thresholds": [thresholds.medium, thresholds.full],
    "readings": asyncio.run(read_all(queries)),
}))
"""


def _csv(name: str) -> list[dict[str, str]]:
    with (GTFS_MINI / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


ROUTE_LINES = {row["route_id"]: row["route_short_name"] for row in _csv("routes.txt")}
TRIPS_BY_LINE: dict[str, list[str]] = {}
for _row in _csv("trips.txt"):
    TRIPS_BY_LINE.setdefault(ROUTE_LINES[_row["route_id"]], []).append(_row["trip_id"])
FORCED_TRIPS = {line: TRIPS_BY_LINE[line][:3] for line in FORCED}
SIMULATED_TRIPS = TRIPS_BY_LINE[SIMULATED_LINE][:20]


def _settings(path: Path) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, env="test", database_url=f"sqlite:///{path}", stop_token_secret="x" * 32
    )


@pytest.fixture(scope="module")
def template_db(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`gtfs_mini` plus a never-expiring override for each line of `FORCED`."""
    path = tmp_path_factory.mktemp("occupancy_composition") / "template.sqlite"
    engine = create_engine(_settings(path))
    init_db(engine)
    use_case = ImportGtfsFeed(CsvGtfsFeedReader, SqliteGtfsFeedWriter(engine), FakeClock(NOW))
    asyncio.run(use_case.execute(ImportGtfsFeedCommand(GTFS_MINI)))
    overrides = SqliteOccupancyOverrideRepository(engine)
    for line, level in FORCED.items():
        overrides.set(OccupancyOverride(line=line, level=level, expires_at=NEVER_EXPIRES))
    engine.dispose()
    return path


@pytest.fixture
def database(tmp_path: Path, template_db: Path) -> Path:
    path = tmp_path / "avisabus.sqlite"
    shutil.copyfile(template_db, path)
    return path


def _mid_trip(network: SqliteNetworkRepository, trip_id: str) -> datetime:
    """Halfway through the scheduled trip, so that the simulation is far from its minimum."""
    arrivals = [stop_time.arrival_s for stop_time in network.trip_stop_times(trip_id)]
    middle_s = (min(arrivals) + max(arrivals)) / 2
    return service_day_start(SERVICE_DATE) + timedelta(seconds=middle_s)


def _queries(database: Path) -> list[tuple[str, str, str]]:
    engine = create_engine(_settings(database))
    try:
        network = SqliteNetworkRepository(engine)
        trips = [trip for trips in FORCED_TRIPS.values() for trip in trips] + SIMULATED_TRIPS
        return [
            (trip, SERVICE_DATE.isoformat(), _mid_trip(network, trip).isoformat()) for trip in trips
        ]
    finally:
        engine.dispose()


def _reference_readings(
    database: Path,
    queries: list[tuple[str, str, str]],
    *,
    capacity: int,
    seats: int,
    seed: str,
    thresholds: OccupancyThresholds,
) -> dict[str, list[int]]:
    """Readings of a sensor built here with the given values and the overrides of the database."""
    engine = create_engine(_settings(database))
    try:
        overrides = InMemoryOccupancyOverrideRepository()
        for override in SqliteOccupancyOverrideRepository(engine).active(NOW):
            overrides.set(override)
        sensor: OccupancySensor = SimulatedOccupancySensor(
            network=SqliteNetworkRepository(engine),
            overrides=overrides,
            clock=FakeClock(NOW),
            capacity=capacity,
            seats=seats,
            seed=seed,
            thresholds=thresholds,
        )

        async def read_all() -> dict[str, list[int]]:
            readings: dict[str, list[int]] = {}
            for trip_id, service_date, at in queries:
                vehicle = VehicleRef(trip_id, date.fromisoformat(service_date))
                reading = await sensor.read(vehicle, datetime.fromisoformat(at))
                assert reading is not None
                readings[trip_id] = [reading.capacity, reading.seats, reading.occupied]
            return readings

        return asyncio.run(read_all())
    finally:
        engine.dispose()


def _run_main(tmp_path: Path, database: Path, probe_args: list[str]) -> dict[str, Any]:
    workdir = tmp_path / "root" / "backend"  # no .env here nor in its parent
    workdir.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("AVISABUS_")}
    env.update(
        {
            "AVISABUS_ENV": "test",
            "AVISABUS_DATABASE_URL": f"sqlite:///{database}",
            # In `test` the arrivals source is the replay (sae_arrivals_source AC-20).
            "AVISABUS_SAE_REPLAY_DIR": str(E01),
            # With a secret, stop_tokens_qr does not log its dev-secret warning on stdout.
            "AVISABUS_STOP_TOKEN_SECRET": "x" * 32,
            **CONFIGURED,
        }
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", PROBE, *probe_args],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    output: dict[str, Any] = json.loads(result.stdout.splitlines()[-1])
    return output


def _level(reading: list[int], thresholds: OccupancyThresholds) -> OccupancyLevel:
    capacity, seats, occupied = reading
    return classify_occupancy(OccupancyReading(capacity, seats, occupied, NOW), thresholds).level


@pytest.mark.spec("occupancy_sensor.AC-15")
def test_main_composes_the_sensor_and_the_classifier_with_the_configured_values(
    tmp_path: Path, database: Path
) -> None:
    queries = _queries(database)
    composed = _run_main(tmp_path, database, [json.dumps(queries)])

    # Classifier: the thresholds that main.py exposes for the use cases are the configured ones.
    assert composed["thresholds"] == [THRESHOLDS.medium, THRESHOLDS.full]

    # Sensor: every reading equals the one of a sensor built with the configured values.
    expected = _reference_readings(
        database, queries, capacity=CAPACITY, seats=SEATS, seed=SEED, thresholds=THRESHOLDS
    )
    assert composed["readings"] == expected
    for reading in composed["readings"].values():
        assert reading[:2] == [CAPACITY, SEATS]

    # Overrides follow the configured thresholds: the forced level is the configured class.
    for line, level in FORCED.items():
        for trip_id in FORCED_TRIPS[line]:
            reading = composed["readings"][trip_id]
            assert reading[2] == override_occupied(level, CAPACITY, THRESHOLDS)
            assert _level(reading, THRESHOLDS) is level


@pytest.mark.spec("occupancy_sensor.AC-15")
def test_the_configuration_of_the_test_is_far_enough_from_the_defaults(database: Path) -> None:
    """Guard of the test above: leaving any single value at its default changes some reading."""
    queries = _queries(database)
    configured = {
        "capacity": CAPACITY,
        "seats": SEATS,
        "seed": SEED,
        "thresholds": THRESHOLDS,
    }
    defaults = Settings(_env_file=None, env="test")  # type: ignore[call-arg]
    default_values = {
        "capacity": defaults.occupancy_capacity,
        "seats": defaults.occupancy_seats,
        "seed": defaults.occupancy_seed,
        "thresholds": defaults.occupancy_thresholds(),
    }
    assert default_values["thresholds"] == DEFAULT_THRESHOLDS
    expected = _reference_readings(database, queries, **configured)  # type: ignore[arg-type]
    for name, default in default_values.items():
        assert configured[name] != default, name
        mutated = _reference_readings(
            database,
            queries,
            **{**configured, name: default},  # type: ignore[arg-type]
        )
        assert mutated != expected, f"a default {name} would go unnoticed"


@pytest.mark.spec("occupancy_sensor.AC-15")
def test_the_cli_container_composes_no_occupancy_sensor_nor_classifier() -> None:
    """The CLI only manages overrides (`occupancy override`): it stores the forced level, not
    places, so it builds neither a sensor nor thresholds that could fall back to the defaults.
    If that changes, this test must become one like the main.py test above."""
    field_types = {field.name: field.type for field in dataclasses.fields(CliContainer)}
    for name, field_type in field_types.items():
        assert isinstance(field_type, type), name
        assert not issubclass(field_type, SimulatedOccupancySensor), name
        assert not issubclass(field_type, OccupancyThresholds), name
        assert "sensor" not in name and "threshold" not in name, name
