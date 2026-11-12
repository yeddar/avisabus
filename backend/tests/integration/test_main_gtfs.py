"""Composition root (`avisabus.main`) with the GTFS state in `/health` and the expiry warning task
(deployment_rpi T-03).

`avisabus.main` builds everything at import time, so it is imported in a subprocess with a
temporary database (without a GTFS feed, so nothing depends on the real date) and working
directory, as in `test_main_driver.py`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.sae import E01

PROBE = """
import asyncio, json
from starlette.testclient import TestClient
import avisabus.main as main

watcher = main.gtfs_expiry_watcher
facts = {
    "state": main.app.state.gtfs_status is main.gtfs_status,
    "same_clock": main.gtfs_status.clock is main.clock and watcher._clock is main.clock,
    "same_network": watcher._network is main.gtfs_status.network,
    "warning_days": watcher._warning_days,
}
with TestClient(main.app) as client:
    response = client.get("/api/v1/health")
    facts["health"] = [response.status_code, response.json()["status"], response.json()["gtfs"]]


def running():
    return sorted(t.get_name() for t in asyncio.all_tasks() if t.get_name().startswith("gtfs."))


async def probe():
    async with main.lifespan(main.app):
        facts["running"] = running()
    facts["after"] = running()


asyncio.run(probe())
print("FACTS " + json.dumps(facts))
"""


def _run_main(tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    workdir = tmp_path / "root" / "backend"
    workdir.mkdir(parents=True)
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AVISABUS_")}
    clean.update(
        {
            "AVISABUS_ENV": "test",
            "AVISABUS_DATABASE_URL": f"sqlite:///{tmp_path / 'avisabus.sqlite'}",
            "AVISABUS_SAE_REPLAY_DIR": str(E01),
            "AVISABUS_STOP_TOKEN_SECRET": "x" * 32,
            **env,
        }
    )
    return subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", PROBE],
        cwd=workdir,
        env=clean,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.spec("deployment_rpi.AC-10")
@pytest.mark.spec("deployment_rpi.AC-11")
def test_main_wires_the_gtfs_state_and_runs_the_expiry_watcher(tmp_path: Path) -> None:
    result = _run_main(tmp_path, AVISABUS_GTFS_EXPIRY_WARNING_DAYS="5")
    assert result.returncode == 0, result.stderr
    (line,) = [line for line in result.stdout.splitlines() if line.startswith("FACTS ")]
    facts = json.loads(line.removeprefix("FACTS "))
    assert facts == {
        "state": True,
        "same_clock": True,
        "same_network": True,
        "warning_days": 5,
        "health": [200, "degraded", None],
        "running": ["gtfs.expiry_watcher"],
        "after": [],
    }
