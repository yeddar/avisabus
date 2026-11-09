"""Alerts through `/ws/passenger`: the confirmation event and the snapshot (alert_create T-05).

`starlette.testclient.TestClient` runs the application in-process, lifespan included (no
network); the SAE is the replayed `stop_508_peak` session and time is a `FakeClock`.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine
from starlette.testclient import TestClient

from tests.support.alerts_app import DEVICE, OTHER_DEVICE, body_for, build_alerts_app, headers
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import STOP_508_PEAK
from tests.support.stops import API, import_feed, new_engine, replay, token
from tests.support.ws import receive_json_soon

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
ENDPOINT = "/ws/passenger"


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("alerts_ws") / "avisabus.sqlite"
    engine = new_engine(path)
    import_feed(engine, GTFS_MINI)
    engine.dispose()
    return path


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(PEAK_START)


@pytest.fixture
def client(mini_feed: Path, tmp_path: Path, clock: FakeClock) -> Iterator[TestClient]:
    path = tmp_path / "avisabus.sqlite"
    path.write_bytes(mini_feed.read_bytes())
    engine: Engine = new_engine(path)
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    built = build_alerts_app(engine, clock, source)
    with TestClient(built.app) as client:
        yield client
    engine.dispose()


def _requestable(client: TestClient, stop_id: str, line: str) -> dict[str, Any]:
    response = client.get(f"{API}/stops/{stop_id}/arrivals", params={"t": token(stop_id)})
    return next(a for a in response.json()["arrivals"] if a["can_alert"] and a["line"] == line)


def _create(client: TestClient, stop_id: str, line: str, device: str = DEVICE) -> Any:
    arrival = _requestable(client, stop_id, line)
    response = client.post(
        f"{API}/alerts",
        json=body_for(arrival, stop_id, token(stop_id), needs=["RAMP"]),
        headers=headers(device),
    )
    assert response.status_code == 201
    return response.json()


@pytest.mark.spec("alert_create.AC-09")
def test_alert_registered_reaches_the_open_socket_of_the_device(client: TestClient) -> None:
    with (
        client.websocket_connect(ENDPOINT) as mine,
        client.websocket_connect(ENDPOINT) as theirs,
    ):
        mine.send_json({"type": "hello", "device_id": DEVICE})
        theirs.send_json({"type": "hello", "device_id": OTHER_DEVICE})
        assert receive_json_soon(mine) == {"type": "alerts.snapshot", "alerts": []}
        assert receive_json_soon(theirs) == {"type": "alerts.snapshot", "alerts": []}
        alert = _create(client, "508", "93")
        # The event is published while the POST is served: no time passes (RNF-02, ≤ 5 s).
        assert receive_json_soon(mine) == {"type": "alert.registered", "alert": alert}
        other = _create(client, "508", "93", OTHER_DEVICE)
        assert receive_json_soon(theirs) == {"type": "alert.registered", "alert": other}


@pytest.mark.spec("alert_create.AC-11")
@pytest.mark.spec("alert_create.AC-10")
def test_hello_gets_the_active_alerts_of_the_device(client: TestClient, clock: FakeClock) -> None:
    first = _create(client, "2070", "98")
    clock.advance(timedelta(seconds=30))
    second = _create(client, "508", "93")
    _create(client, "508", "93", OTHER_DEVICE)
    mine = client.get(f"{API}/alerts/mine", headers=headers()).json()
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json({"type": "hello", "device_id": DEVICE})
        snapshot = receive_json_soon(ws)
    assert snapshot == {"type": "alerts.snapshot", "alerts": [first, second]}
    assert snapshot["alerts"] == mine["alerts"]


@pytest.mark.spec("alert_create.AC-11")
def test_a_device_without_alerts_gets_an_empty_snapshot(client: TestClient) -> None:
    _create(client, "508", "93", OTHER_DEVICE)
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json({"type": "hello", "device_id": DEVICE})
        assert receive_json_soon(ws) == {"type": "alerts.snapshot", "alerts": []}


def test_the_snapshot_is_read_at_each_hello(client: TestClient) -> None:
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json({"type": "hello", "device_id": DEVICE})
        assert receive_json_soon(ws)["alerts"] == []
    alert = _create(client, "508", "93")
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json({"type": "hello", "device_id": DEVICE})
        assert receive_json_soon(ws)["alerts"] == [alert]
