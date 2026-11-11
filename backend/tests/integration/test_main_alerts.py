"""Composition root (`avisabus.main`) with the alert endpoints (alert_create T-05).

`avisabus.main` builds everything at import time, so it is imported in a subprocess with a
temporary database (without a GTFS feed) and working directory, as in `test_main_realtime.py`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.sae import E01

PROBE = """
import json, sqlite3, sys
from starlette.testclient import TestClient
import avisabus.main as main

create = main.alert_use_cases.create_alert
facts = {
    "drivers": type(create._drivers).__name__,
    "limiter": type(create._device_limiter).__name__,
    "max_age_s": create._max_age.total_seconds(),
    "max_lead_s": main.stop_use_cases.get_stop_arrivals._alert_max_lead.total_seconds(),
    "same_arrivals": create._stop_arrivals is main.stop_use_cases.get_stop_arrivals,
    "same_publisher": create._events is main.realtime.publisher,
    "snapshots": type(main.realtime.passenger.snapshots).__name__,
}
device = {"X-Device-Id": "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"}
body = {"stop_id": "508", "token": "A" * 22, "line": "93", "direction_id": 0,
        "trip_id": "t", "service_date": "2026-11-04", "needs": []}
with TestClient(main.app) as client:
    mine = client.get("/api/v1/alerts/mine", headers=device)
    facts["mine"] = [mine.status_code, mine.headers["cache-control"], mine.json()]
    facts["posts"] = [
        client.post("/api/v1/alerts", json=body, headers=device).status_code for _ in range(3)
    ]
db = sqlite3.connect(sys.argv[1])
facts["table"] = db.execute("SELECT name FROM sqlite_master WHERE name = 'alert'").fetchone()
print("FACTS " + json.dumps(facts))
"""


def _run_main(tmp_path: Path, **env: str) -> subprocess.CompletedProcess[str]:
    workdir = tmp_path / "root" / "backend"
    workdir.mkdir(parents=True)
    database = tmp_path / "avisabus.sqlite"
    clean = {k: v for k, v in os.environ.items() if not k.startswith("AVISABUS_")}
    clean.update(
        {
            "AVISABUS_ENV": "test",
            "AVISABUS_DATABASE_URL": f"sqlite:///{database}",
            "AVISABUS_SAE_REPLAY_DIR": str(E01),
            "AVISABUS_STOP_TOKEN_SECRET": "x" * 32,
            **env,
        }
    )
    return subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", PROBE, str(database)],
        cwd=workdir,
        env=clean,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


@pytest.mark.spec("alert_create.AC-08")
@pytest.mark.spec("alert_create.AC-11")
def test_main_wires_the_alerts_with_their_configuration(tmp_path: Path) -> None:
    result = _run_main(
        tmp_path,
        AVISABUS_ALERT_RATE_DEVICE="2",
        AVISABUS_ALERT_MAX_AGE_MIN="20",
        AVISABUS_ALERT_MAX_LEAD_MIN="25",
    )
    assert result.returncode == 0, result.stderr
    (line,) = [line for line in result.stdout.splitlines() if line.startswith("FACTS ")]
    facts = json.loads(line.removeprefix("FACTS "))
    assert facts == {
        "drivers": "SessionDriverDirectory",
        "limiter": "InMemoryRateLimiter",
        "max_age_s": 1200,
        "max_lead_s": 1500,
        "same_arrivals": True,
        "same_publisher": True,
        "snapshots": "AlertSnapshotProvider",
        "mine": [200, "no-store", {"alerts": []}],
        # Invalid token: 404 twice (they count) and then the device limit of 2.
        "posts": [404, 404, 429],
        "table": ["alert"],
    }
