"""Composition root (`avisabus.main`) with the real-time components (realtime_events T-04).

`avisabus.main` builds everything at import time, so it is imported in a subprocess with a
temporary database and working directory (as in `test_main_composition.py`). The probe opens
`/ws/passenger` in-process with Starlette's `TestClient` (no network) and stops the application.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.support.sae import E01

PROBE = """
import json
from starlette.testclient import TestClient
import avisabus.main as main

passenger = main.realtime.passenger
facts = {
    "publisher": type(main.realtime.publisher).__name__,
    "hasher": type(main.realtime.hasher).__name__,
    "snapshots": type(passenger.snapshots).__name__,
    "hello_timeout_s": passenger.hello_timeout_s,
    "ping_interval_s": passenger.ping_interval_s,
}
with TestClient(main.app) as client:
    ws = client.websocket_connect("/ws/passenger").__enter__()
    ws.send_json({"type": "hello", "device_id": "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"})
    facts["snapshot"] = ws.receive_json()
    facts["subscriptions"] = main.realtime.publisher.subscriber_count()
    client.portal.call(client.wait_shutdown)
    facts["on_stop"] = ws.receive()
    ws.__exit__(None, None, None)

    async def stopped():
        return None

    client.wait_shutdown = stopped
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


@pytest.mark.spec("realtime_events.AC-07")
@pytest.mark.spec("realtime_events.AC-11")
def test_main_mounts_the_passenger_socket_and_closes_it_on_stop(tmp_path: Path) -> None:
    result = _run_main(tmp_path, AVISABUS_WS_HELLO_TIMEOUT_S="7", AVISABUS_WS_PING_INTERVAL_S="40")
    assert result.returncode == 0, result.stderr
    (line,) = [line for line in result.stdout.splitlines() if line.startswith("FACTS ")]
    facts = json.loads(line.removeprefix("FACTS "))
    assert facts == {
        "publisher": "InMemoryEventPublisher",
        "hasher": "HmacDeviceHasher",
        "snapshots": "EmptySnapshotProvider",
        "hello_timeout_s": 7,
        "ping_interval_s": 40,
        "snapshot": {"type": "alerts.snapshot", "alerts": []},
        "subscriptions": 1,
        "on_stop": {"type": "websocket.close", "code": 1001, "reason": ""},
    }
