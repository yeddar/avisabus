"""`DELETE /api/v1/alerts/{alert_id}` over `gtfs_mini` and the replayed `stop_508_peak` session
(alert_cancel T-02).

Each alert is created with `POST /alerts` in the same test, for a bus shown by `GET /arrivals`
with the same `FakeClock`. The `alert.cancelled` event is read from `/ws/passenger`
(`starlette.testclient.TestClient` runs the application in-process: no network).
"""

import asyncio
import contextlib
import json
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text
from starlette.testclient import TestClient
from structlog.testing import capture_logs

from avisabus.adapters.inbound.http.app import openapi_document
from avisabus.adapters.outbound.persistence.sqlite_alerts import SqliteAlertRepository
from avisabus.domain.models.events import Event
from avisabus.domain.ports.events import Subscription, device_channel
from tests.support.alerts_app import (
    DEVICE,
    OTHER_DEVICE,
    PROBLEM_BASE,
    AlertsApp,
    alerts_client,
    body_for,
    build_alerts_app,
    headers,
)
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import E01, STOP_508_PEAK
from tests.support.stops import API, import_feed, new_engine, replay, token
from tests.support.ws import receive_json_soon

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
ALERTS = f"{API}/alerts"
WS = "/ws/passenger"
PROBLEM_JSON = "application/problem+json"
NOT_FOUND = {"type": PROBLEM_BASE + "alert-not-found", "title": "Not Found", "status": 404}


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`gtfs_mini` imported once; each test copies the database file (alerts are per test)."""
    path = tmp_path_factory.mktemp("alerts_cancel") / "avisabus.sqlite"
    engine = new_engine(path)
    import_feed(engine, GTFS_MINI)
    engine.dispose()
    return path


@pytest.fixture
def engine(mini_feed: Path, tmp_path: Path) -> Iterator[Engine]:
    path = tmp_path / "avisabus.sqlite"
    path.write_bytes(mini_feed.read_bytes())
    engine = new_engine(path)
    yield engine
    engine.dispose()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(PEAK_START)


async def _create(
    client: httpx.AsyncClient, line: str = "93", device: str = DEVICE
) -> dict[str, Any]:
    arrivals = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
    arrival = next(a for a in arrivals.json()["arrivals"] if a["can_alert"] and a["line"] == line)
    response = await client.post(
        ALERTS,
        json=body_for(arrival, "508", token("508"), needs=["RAMP", "VISUAL"]),
        headers=headers(device),
    )
    assert response.status_code == 201
    created: dict[str, Any] = response.json()
    return created


async def _delete(
    client: httpx.AsyncClient, alert_id: str, device: str | None = DEVICE
) -> httpx.Response:
    sent = {} if device is None else headers(device)
    return await client.delete(f"{ALERTS}/{alert_id}", headers=sent)


def _rows(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT alert_id, needs FROM alert ORDER BY alert_id"))
        return [(row[0], row[1]) for row in rows]


def _subscribe_both(built: AlertsApp) -> list[Subscription]:
    """Subscriptions of both devices' channels, to check that nothing is published."""
    publisher = built.realtime.publisher
    return [
        publisher.subscribe(device_channel(built.device_hash(device)))
        for device in (DEVICE, OTHER_DEVICE)
    ]


async def _queued_event(subscription: Subscription) -> Event | None:
    """The event already queued in the subscription, if any, without letting time pass: the
    publisher is synchronous, so an event of a request is queued when its response arrives."""
    task = asyncio.ensure_future(subscription.next_event())
    await asyncio.sleep(0)  # one turn of the loop, no real wait
    if task.done():
        return task.result()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return None


# --- Cancellation (AC-01) ---


@pytest.mark.spec("alert_cancel.AC-01")
@pytest.mark.spec("alert_cancel.AC-05")
def test_cancelling_deletes_the_alert_and_tells_the_device_sockets(
    engine: Engine, clock: FakeClock
) -> None:
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    built = build_alerts_app(engine, clock, source)
    with TestClient(built.app) as client:
        arrivals = client.get(f"{API}/stops/508/arrivals", params={"t": token("508")}).json()
        arrival = next(a for a in arrivals["arrivals"] if a["can_alert"] and a["line"] == "93")
        body = body_for(arrival, "508", token("508"), needs=["RAMP", "VISUAL"])
        created = client.post(ALERTS, json=body, headers=headers()).json()
        theirs = client.post(ALERTS, json=body, headers=headers(OTHER_DEVICE)).json()
        with (
            client.websocket_connect(WS) as tab,
            client.websocket_connect(WS) as other_tab,
            client.websocket_connect(WS) as other_device,
        ):
            for ws, device in ((tab, DEVICE), (other_tab, DEVICE), (other_device, OTHER_DEVICE)):
                ws.send_json({"type": "hello", "device_id": device})
                assert receive_json_soon(ws)["type"] == "alerts.snapshot"
            response = client.delete(f"{ALERTS}/{created['alert_id']}", headers=headers())
            assert response.status_code == 204  # else no event: fail instead of waiting for it
            # The row is gone, with its needs; the other device's alert is untouched.
            rows = _rows(engine)
            mine = client.get(f"{ALERTS}/mine", headers=headers()).json()
            # Published while the DELETE is served: every socket of the device gets it at once.
            cancelled = {"type": "alert.cancelled", "alert_id": created["alert_id"]}
            assert receive_json_soon(tab) == cancelled
            assert receive_json_soon(other_tab) == cancelled
            # The other device's socket did not get it: its first event is its own cancellation.
            theirs_cancelled = client.delete(
                f"{ALERTS}/{theirs['alert_id']}", headers=headers(OTHER_DEVICE)
            )
            assert theirs_cancelled.status_code == 204
            assert receive_json_soon(other_device) == {
                "type": "alert.cancelled",
                "alert_id": theirs["alert_id"],
            }
    assert response.status_code == 204
    assert response.content == b""
    assert response.headers["Cache-Control"] == "no-store"
    assert mine == {"alerts": []}
    assert rows == [(theirs["alert_id"], "RAMP,VISUAL")]


@pytest.mark.spec("alert_cancel.AC-01")
async def test_a_cancelled_line_can_be_requested_again(engine: Engine, clock: FakeClock) -> None:
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        first = await _create(client)
        assert (await _delete(client, first["alert_id"])).status_code == 204
        second = await _create(client)  # 201: no active alert left at that stop and line
    assert second["alert_id"] != first["alert_id"]
    assert _rows(engine) == [(second["alert_id"], "RAMP,VISUAL")]


# --- Not found (AC-02) ---


@pytest.mark.spec("alert_cancel.AC-02")
@pytest.mark.spec("alert_cancel.AC-05")
async def test_unknown_expired_or_foreign_alerts_are_the_same_404(
    engine: Engine, clock: FakeClock
) -> None:
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, built):
        mine = await _create(client, "93")
        expired = await _create(client, "70")
        theirs = await _create(client, "93", OTHER_DEVICE)
        # `alert_expiry` deletes the expired alerts.
        assert SqliteAlertRepository(engine).delete(expired["alert_id"])
        before = _rows(engine)
        subscriptions = _subscribe_both(built)
        responses = {
            "unknown": await _delete(client, str(uuid.uuid4())),
            "not a uuid": await _delete(client, "not-an-alert"),
            "expired": await _delete(client, expired["alert_id"]),
            "other device": await _delete(client, theirs["alert_id"]),
            "theirs, from their device": await _delete(client, mine["alert_id"], OTHER_DEVICE),
        }
        queued = [await _queued_event(s) for s in subscriptions]
        for subscription in subscriptions:
            subscription.close()
        after = _rows(engine)
    for name, response in responses.items():
        assert response.status_code == 404, name
        assert response.headers["content-type"] == PROBLEM_JSON, name
        assert response.headers["Cache-Control"] == "no-store", name
        assert response.json() == NOT_FOUND, name
    assert len({r.content for r in responses.values()}) == 1  # same body in every case
    assert after == before
    assert queued == [None, None]


@pytest.mark.spec("alert_cancel.AC-02")
async def test_an_alert_can_only_be_cancelled_once(engine: Engine, clock: FakeClock) -> None:
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        alert = await _create(client)
        first = await _delete(client, alert["alert_id"])
        again = await _delete(client, alert["alert_id"])
    assert (first.status_code, again.status_code) == (204, 404)
    assert again.json() == NOT_FOUND


# --- Device header (AC-03) ---


@pytest.mark.spec("alert_cancel.AC-03")
@pytest.mark.spec("alert_cancel.AC-05")
@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "not-a-uuid",
        "3F2B8C1E-9A4D-4E6F-8B2A-1C3D5E7F9A0B",  # not canonical
        "3f2b8c1e-9a4d-1e6f-8b2a-1c3d5e7f9a0b",  # version 1
    ],
)
async def test_missing_or_invalid_device_id_is_a_400(
    engine: Engine, clock: FakeClock, header: str | None
) -> None:
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        alert = await _create(client)
        sent = {} if header is None else {"X-Device-Id": header}
        responses = [
            await client.delete(f"{ALERTS}/{alert['alert_id']}", headers=sent),
            await client.delete(f"{ALERTS}/{uuid.uuid4()}", headers=sent),
        ]
    for response in responses:
        assert response.status_code == 400
        assert response.headers["content-type"] == PROBLEM_JSON
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json() == {
            "type": PROBLEM_BASE + "invalid-device-id",
            "title": "Bad Request",
            "status": 400,
        }
    assert [row[0] for row in _rows(engine)] == [alert["alert_id"]]


# --- Logs, headers and contract (AC-05) ---


@pytest.mark.spec("alert_cancel.AC-05")
async def test_cancellation_is_logged_without_personal_data(
    engine: Engine, clock: FakeClock
) -> None:
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    with capture_logs() as logs:
        async with alerts_client(engine, clock, source) as (client, built):
            alert = await _create(client)
            await _delete(client, str(uuid.uuid4()))
            await _delete(client, alert["alert_id"], OTHER_DEVICE)
            await _delete(client, alert["alert_id"])
            device_hash = built.device_hash()
    cancelled = [
        {k: v for k, v in log.items() if k != "log_level"}
        for log in logs
        if log["event"] == "alert.cancelled"
    ]
    assert cancelled == [
        {"event": "alert.cancelled", "alert_id": alert["alert_id"], "stop_id": "508", "line": "93"}
    ]
    logged = json.dumps([log for log in logs if log["event"] != "alert.created"], default=str)
    for secret in (DEVICE, OTHER_DEVICE, device_hash, "RAMP", "VISUAL", "needs"):
        assert secret not in logged


class _FailingCancel:
    async def execute(self, device_hash: str, alert_id: str) -> None:
        raise RuntimeError("database is locked")


@pytest.mark.spec("alert_cancel.AC-05")
async def test_an_unexpected_error_is_not_stored_either(engine: Engine, clock: FakeClock) -> None:
    """A `500` is built outside the application middleware: it gets `no-store` itself."""
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, built):
        state = built.app.state
        state.alert_use_cases = replace(state.alert_use_cases, cancel_alert=_FailingCancel())
        response = await _delete(client, str(uuid.uuid4()))
    assert response.status_code == 500
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json() == {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
    }


@pytest.mark.spec("alert_cancel.AC-05")
def test_openapi_describes_the_cancel_endpoint() -> None:
    document = openapi_document()
    cancel = document["paths"]["/api/v1/alerts/{alert_id}"]["delete"]
    assert {"204", "400", "404"} <= set(cancel["responses"])
    assert not {"200", "201"} & set(cancel["responses"])
    assert "content" not in cancel["responses"]["204"]
    for status, problem in (("400", "invalid-device-id"), ("404", "alert-not-found")):
        example = cancel["responses"][status]["content"]["application/problem+json"]["example"]
        assert example["type"] == PROBLEM_BASE + problem
    assert {(p["name"], p["in"]) for p in cancel["parameters"]} == {
        ("alert_id", "path"),
        ("x-device-id", "header"),
    }
    alert_id = next(p for p in cancel["parameters"] if p["name"] == "alert_id")
    assert alert_id["schema"]["type"] == "string"


# --- Composition root ---

PROBE = """
import json
from starlette.testclient import TestClient
import avisabus.main as main

cancel = main.alert_use_cases.cancel_alert
facts = {
    "notifier": type(cancel._drivers).__name__,
    "same_publisher": cancel._events is main.realtime.publisher,
}
device = {"X-Device-Id": "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"}
with TestClient(main.app) as client:
    response = client.delete("/api/v1/alerts/6f1c0d6e-3b9a-4c2e-9f4d-2a7b8c9d0e1f", headers=device)
    facts["delete"] = [response.status_code, response.headers["cache-control"], response.json()]
print("FACTS " + json.dumps(facts))
"""


@pytest.mark.spec("alert_cancel.AC-02")
@pytest.mark.spec("alert_cancel.AC-04")
def test_main_wires_the_cancellation(tmp_path: Path) -> None:
    """`avisabus.main` builds everything at import time: it runs in a subprocess with a temporary
    database, as in `test_main_alerts.py`."""
    workdir = tmp_path / "root" / "backend"
    workdir.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("AVISABUS_")}
    env.update(
        {
            "AVISABUS_ENV": "test",
            "AVISABUS_DATABASE_URL": f"sqlite:///{tmp_path / 'avisabus.sqlite'}",
            "AVISABUS_SAE_REPLAY_DIR": str(E01),
            "AVISABUS_STOP_TOKEN_SECRET": "x" * 32,
        }
    )
    result = subprocess.run(  # noqa: S603 - fixed interpreter and script
        [sys.executable, "-c", PROBE],
        cwd=workdir,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    line = next(line for line in result.stdout.splitlines() if line.startswith("FACTS "))
    facts = json.loads(line.removeprefix("FACTS "))
    assert facts == {
        "notifier": "DemandViewNotifier",
        "same_publisher": True,
        "delete": [404, "no-store", NOT_FOUND],
    }
