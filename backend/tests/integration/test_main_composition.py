"""Composition root (`avisabus.main`) with the occupancy sensor (occupancy_sensor T-06).

`avisabus.main` builds everything at import time, so it is imported in a subprocess with a
temporary database and working directory: the tests never touch `data/` nor a developer `.env`.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

PROBE = """
import sqlite3, sys
import avisabus.main as main
from avisabus.domain.ports.occupancy import OccupancySensor
sensor: OccupancySensor = main.occupancy_sensor
print(type(sensor).__name__)
print(main.occupancy_thresholds)
db = sqlite3.connect(sys.argv[1])
print(db.execute("SELECT name FROM sqlite_master WHERE name = 'occupancy_override'").fetchone())
"""


def _run_main(tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    workdir = tmp_path / "root" / "backend"  # no .env here nor in its parent
    workdir.mkdir(parents=True)
    database = tmp_path / "avisabus.sqlite"
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AVISABUS_")}
    clean.update({"AVISABUS_ENV": "test", "AVISABUS_DATABASE_URL": f"sqlite:///{database}"})
    # With a secret, stop_tokens_qr does not log its dev-secret warning on stdout.
    clean.update({"AVISABUS_STOP_TOKEN_SECRET": "x" * 32, **env})
    return subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", PROBE, str(database)],
        cwd=workdir,
        env=clean,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def test_main_builds_the_simulated_sensor_and_creates_the_override_table(
    tmp_path: Path,
) -> None:
    result = _run_main(
        tmp_path,
        AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM="0.4",
        AVISABUS_OCCUPANCY_THRESHOLD_FULL="0.9",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "SimulatedOccupancySensor",
        "OccupancyThresholds(medium=0.4, full=0.9)",
        "('occupancy_override',)",
    ]


@pytest.mark.spec("occupancy_sensor.AC-03")
@pytest.mark.parametrize(
    "env",
    [
        {"AVISABUS_OCCUPANCY_SEATS": "91"},
        {"AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM": "0.9", "AVISABUS_OCCUPANCY_THRESHOLD_FULL": "0.8"},
    ],
)
def test_application_refuses_to_start_with_invalid_occupancy_configuration(
    tmp_path: Path, env: dict[str, str]
) -> None:
    result = _run_main(tmp_path, **env)
    assert result.returncode != 0
    assert "ConfigurationError" in result.stderr
    assert not (tmp_path / "avisabus.sqlite").exists()
