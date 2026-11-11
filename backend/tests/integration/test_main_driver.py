"""Composition root (`avisabus.main`) with the driver endpoints and the reaper (driver_session
T-06).

`avisabus.main` builds everything at import time, so it is imported in a subprocess with a
temporary database (without a GTFS feed) and working directory, as in `test_main_alerts.py`.
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

use_cases = main.driver_use_cases
facts = {
    "listener": type(use_cases.end_session._close._listener).__name__,
    "idle_s": use_cases.reap._idle_timeout.total_seconds(),
    "interval_s": use_cases.reaper_interval.total_seconds(),
    "same_clock": use_cases.reap._clock is main.clock,
}
with TestClient(main.app) as client:
    unknown = client.post("/api/v1/driver/sessions", json={"code": "00000000"})
    facts["login"] = [unknown.status_code, unknown.json()["type"], unknown.headers["cache-control"]]
    facts["no_token"] = client.get("/api/v1/driver/sessions/current").status_code
    facts["view_no_token"] = client.get("/api/v1/driver/sessions/current/view").status_code
    with client.websocket_connect("/ws/driver") as ws:
        ws.send_json({"type": "hello", "session_token": "nope"})
        facts["ws_first"] = ws.receive()


def running(prefix="driver."):
    return sorted(t.get_name() for t in asyncio.all_tasks() if t.get_name().startswith(prefix))


async def probe():
    async with main.lifespan(main.app):
        facts["running"] = running()
        facts["demand_running"] = running("demand.")
    facts["after"] = running()
    facts["demand_after"] = running("demand.")


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


def _facts(result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    assert result.returncode == 0, result.stderr
    line = next(ln for ln in result.stdout.splitlines() if ln.startswith("FACTS "))
    facts: dict[str, object] = json.loads(line.removeprefix("FACTS "))
    return facts


@pytest.mark.spec("driver_session.AC-13")
def test_the_application_starts_and_stops_the_reaper(tmp_path: Path) -> None:
    facts = _facts(_run_main(tmp_path, AVISABUS_DRIVER_REAPER_INTERVAL_S="45"))
    assert facts["running"] == ["driver.session_reaper"]
    assert facts["after"] == []
    assert facts["interval_s"] == 45.0
    assert facts["idle_s"] == 600.0
    assert facts["same_clock"] is True


@pytest.mark.spec("driver_session.AC-13")
def test_main_wires_the_driver_endpoints_with_the_demand_listener(tmp_path: Path) -> None:
    facts = _facts(_run_main(tmp_path))
    assert facts["listener"] == "DemandSessionListener"
    assert facts["login"] == [
        401,
        "https://avisabus/problems/invalid-driver-code",
        "no-store",
    ]
    assert facts["no_token"] == 401


@pytest.mark.spec("driver_demand.AC-08")
@pytest.mark.spec("driver_demand.AC-10")
def test_main_exposes_the_socket_and_the_view_of_the_driver(tmp_path: Path) -> None:
    facts = _facts(_run_main(tmp_path))
    assert facts["view_no_token"] == 401
    assert facts["ws_first"] == {"type": "websocket.close", "code": 4401, "reason": ""}


@pytest.mark.spec("driver_demand.AC-09")
def test_the_application_starts_and_stops_the_refresh_of_the_views(tmp_path: Path) -> None:
    facts = _facts(_run_main(tmp_path))
    assert facts["demand_running"] == ["demand.view_refresher"]
    assert facts["demand_after"] == []
