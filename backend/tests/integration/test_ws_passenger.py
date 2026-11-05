"""Passenger WebSocket `/ws/passenger` (realtime_events T-04).

`starlette.testclient.TestClient.websocket_connect` runs the application in-process (no network).
Time never passes for real: the waits (hello timeout, ping interval, `ws.stats`) go through a
fake `sleep` that either returns at once or never, depending on the test.
"""

from collections.abc import Callable, Iterator, Mapping
from typing import Any

import pytest
from fastapi import FastAPI
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import Realtime, build_realtime
from avisabus.adapters.outbound.security.hmac_device_hasher import HmacDeviceHasher
from avisabus.config import Settings
from avisabus.domain.models.device import parse_device_id
from avisabus.domain.models.events import Event
from avisabus.domain.ports.events import device_channel
from tests.conftest import DEFAULT_NOW
from tests.support.fake_clock import FakeClock
from tests.support.ws import FakeSleep, wait_until_closed

ENDPOINT = "/ws/passenger"
DEVICE = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
OTHER_DEVICE = "00000000-0000-4000-8000-000000000000"
HELLO = {"type": "hello", "device_id": DEVICE}
SNAPSHOT_EMPTY = {"type": "alerts.snapshot", "alerts": []}


class RecordingSnapshots:
    """Snapshot provider that records its calls and can run something while it is called."""

    def __init__(
        self,
        alerts: list[Mapping[str, object]] | None = None,
        during: Callable[[str], None] | None = None,
    ) -> None:
        self.alerts = alerts or []
        self.during = during
        self.calls: list[str] = []

    async def active_alerts(self, device_hash: str) -> list[Mapping[str, object]]:
        self.calls.append(device_hash)
        if self.during is not None:
            self.during(device_hash)
        return self.alerts


def _device_hash(settings: Settings, device: str = DEVICE) -> str:
    return HmacDeviceHasher(settings.stop_token_secret_bytes()).hash(parse_device_id(device))


def _build(
    settings: Settings,
    *,
    sleep: FakeSleep | None = None,
    snapshots: RecordingSnapshots | None = None,
    **overrides: Any,
) -> tuple[FastAPI, Realtime]:
    settings = settings.model_copy(update=overrides)
    realtime = build_realtime(
        settings, FakeClock(DEFAULT_NOW), snapshots=snapshots, sleep=sleep or FakeSleep()
    )
    return create_app(settings, realtime=realtime), realtime


@pytest.fixture
def client_for() -> Iterator[Callable[[FastAPI], TestClient]]:
    clients: list[TestClient] = []

    def open_client(app: FastAPI) -> TestClient:
        client = TestClient(app)
        client.__enter__()
        clients.append(client)
        return client

    yield open_client
    for client in reversed(clients):
        client.__exit__(None, None, None)


def _publish(client: TestClient, realtime: Realtime, channel: str, *events: Event) -> None:
    """Publish in the application's event loop, all in one go."""

    def publish_all() -> None:
        for event in events:
            realtime.publisher.publish(channel, event)

    assert client.portal is not None
    client.portal.call(publish_all)


def _event(n: int) -> Event:
    return Event(type="alert.test", payload={"n": n})


# --- AC-06: hello ------------------------------------------------------------------------------


@pytest.mark.spec("realtime_events.AC-06")
def test_closes_with_4408_when_no_hello_arrives_in_5_seconds(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    sleep = FakeSleep({5: 1})  # the hello wait times out at once
    app, realtime = _build(settings, sleep=sleep)
    client = client_for(app)
    with client.websocket_connect(ENDPOINT) as ws:
        assert ws.receive() == {"type": "websocket.close", "code": 4408, "reason": ""}
    assert 5 in sleep.calls
    wait_until_closed(client, realtime.registry)
    assert realtime.publisher.subscriber_count() == 0


@pytest.mark.spec("realtime_events.AC-06")
def test_hello_timeout_is_configurable(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    sleep = FakeSleep({0.5: 1})
    app, _ = _build(settings, sleep=sleep, ws_hello_timeout_s=0.5)
    with client_for(app).websocket_connect(ENDPOINT) as ws:
        assert ws.receive()["code"] == 4408
    assert 0.5 in sleep.calls


@pytest.mark.spec("realtime_events.AC-06")
@pytest.mark.parametrize(
    "message",
    [
        "not json",
        "",
        "[]",
        '"hello"',
        "null",
        '{"type": "hello"}',
        '{"device_id": "' + DEVICE + '"}',
        '{"type": "pong", "device_id": "' + DEVICE + '"}',
        '{"type": "HELLO", "device_id": "' + DEVICE + '"}',
        '{"type": "hello", "device_id": "' + DEVICE.upper() + '"}',
        '{"type": "hello", "device_id": "not-a-uuid"}',
        '{"type": "hello", "device_id": null}',
        '{"type": "hello", "device_id": 42}',
        '{"type": "hello", "device_id": ["' + DEVICE + '"]}',
    ],
)
def test_closes_with_4400_when_the_hello_is_invalid(
    settings: Settings, client_for: Callable[[FastAPI], TestClient], message: str
) -> None:
    snapshots = RecordingSnapshots()
    app, realtime = _build(settings, snapshots=snapshots)
    client = client_for(app)
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_text(message)
        assert ws.receive() == {"type": "websocket.close", "code": 4400, "reason": ""}
    wait_until_closed(client, realtime.registry)
    assert snapshots.calls == []
    assert realtime.publisher.subscriber_count() == 0


@pytest.mark.spec("realtime_events.AC-06")
def test_closes_with_4400_when_the_hello_is_a_binary_frame(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    app, _ = _build(settings)
    with client_for(app).websocket_connect(ENDPOINT) as ws:
        ws.send_bytes(b'{"type": "hello", "device_id": "' + DEVICE.encode() + b'"}')
        assert ws.receive()["code"] == 4400


# --- AC-07: subscription, snapshot and events ----------------------------------------------------


@pytest.mark.spec("realtime_events.AC-07")
def test_valid_hello_gets_an_empty_snapshot_by_default(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    app, realtime = _build(settings)
    with client_for(app).websocket_connect(ENDPOINT) as ws:
        ws.send_json(HELLO)
        assert ws.receive_json() == SNAPSHOT_EMPTY
        channel = device_channel(_device_hash(settings))
        assert realtime.publisher.subscriber_count(channel) == 1


@pytest.mark.spec("realtime_events.AC-07")
@pytest.mark.spec("realtime_events.AC-01")
def test_subscribes_before_the_snapshot_and_forwards_events_after_it_in_order(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    channel = device_channel(_device_hash(settings))
    holder: dict[str, Realtime] = {}

    def publish_during_snapshot(device_hash: str) -> None:
        # Already subscribed: this event must not be lost, and must come after the snapshot.
        assert holder["realtime"].publisher.subscriber_count(device_channel(device_hash)) == 1
        holder["realtime"].publisher.publish(device_channel(device_hash), _event(0))

    snapshots = RecordingSnapshots(
        alerts=[{"alert_id": "a1", "stop_id": "508"}], during=publish_during_snapshot
    )
    app, realtime = _build(settings, snapshots=snapshots)
    holder["realtime"] = realtime
    client = client_for(app)
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json(HELLO)
        assert ws.receive_json() == {
            "type": "alerts.snapshot",
            "alerts": [{"alert_id": "a1", "stop_id": "508"}],
        }
        assert ws.receive_json() == {"type": "alert.test", "n": 0}
        _publish(client, realtime, channel, _event(1), _event(2), _event(3))
        assert [ws.receive_json() for _ in range(3)] == [
            {"type": "alert.test", "n": 1},
            {"type": "alert.test", "n": 2},
            {"type": "alert.test", "n": 3},
        ]
    assert snapshots.calls == [_device_hash(settings)]


@pytest.mark.spec("realtime_events.AC-07")
@pytest.mark.spec("realtime_events.AC-01")
def test_receives_only_the_events_of_its_own_device(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    app, realtime = _build(settings)
    client = client_for(app)
    mine = device_channel(_device_hash(settings))
    other = device_channel(_device_hash(settings, OTHER_DEVICE))
    with client.websocket_connect(ENDPOINT) as ws, client.websocket_connect(ENDPOINT) as ws2:
        ws.send_json(HELLO)
        ws2.send_json({"type": "hello", "device_id": OTHER_DEVICE})
        assert ws.receive_json() == SNAPSHOT_EMPTY
        assert ws2.receive_json() == SNAPSHOT_EMPTY
        _publish(client, realtime, other, _event(1))
        _publish(client, realtime, mine, _event(2))
        assert ws.receive_json() == {"type": "alert.test", "n": 2}
        assert ws2.receive_json() == {"type": "alert.test", "n": 1}


# --- AC-08: ping and client messages -------------------------------------------------------------


@pytest.mark.spec("realtime_events.AC-08")
def test_sends_ping_every_25_seconds(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    sleep = FakeSleep({25: 2})  # two intervals elapse, the third never does
    app, realtime = _build(settings, sleep=sleep)
    client = client_for(app)
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json(HELLO)
        assert ws.receive_json() == SNAPSHOT_EMPTY
        assert ws.receive_json() == {"type": "ping"}
        assert ws.receive_json() == {"type": "ping"}
        _publish(client, realtime, device_channel(_device_hash(settings)), _event(1))
        assert ws.receive_json() == {"type": "alert.test", "n": 1}
    assert sleep.calls.count(25) == 3


@pytest.mark.spec("realtime_events.AC-08")
def test_ping_interval_is_configurable(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    sleep = FakeSleep({0.25: 1})
    app, _ = _build(settings, sleep=sleep, ws_ping_interval_s=0.25)
    with client_for(app).websocket_connect(ENDPOINT) as ws:
        ws.send_json(HELLO)
        assert ws.receive_json() == SNAPSHOT_EMPTY
        assert ws.receive_json() == {"type": "ping"}
    assert 0.25 in sleep.calls


@pytest.mark.spec("realtime_events.AC-08")
def test_ignores_pong_and_any_other_client_message(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    app, realtime = _build(settings)
    client = client_for(app)
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json(HELLO)
        assert ws.receive_json() == SNAPSHOT_EMPTY
        ws.send_json({"type": "pong"})
        ws.send_text("not json")
        ws.send_bytes(b"\x00\x01")
        ws.send_json({"type": "hello", "device_id": OTHER_DEVICE})
        ws.send_json({"type": "subscribe", "channel": "device:x"})
        _publish(client, realtime, device_channel(_device_hash(settings)), _event(1))
        # Nothing answered the client's messages and the connection is still open.
        assert ws.receive_json() == {"type": "alert.test", "n": 1}
        assert realtime.publisher.subscriber_count() == 1
        assert (
            realtime.publisher.subscriber_count(
                device_channel(_device_hash(settings, OTHER_DEVICE))
            )
            == 0
        )


# --- AC-09: overflow -----------------------------------------------------------------------------


@pytest.mark.spec("realtime_events.AC-09")
@pytest.mark.spec("realtime_events.AC-03")
def test_closes_with_4429_when_the_subscription_overflows(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    app, realtime = _build(settings, event_queue_size=2)
    client = client_for(app)
    channel = device_channel(_device_hash(settings))
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json(HELLO)
        assert ws.receive_json() == SNAPSHOT_EMPTY
        _publish(client, realtime, channel, _event(1), _event(2), _event(3))
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_json()
        assert closed.value.code == 4429
    wait_until_closed(client, realtime.registry)
    assert realtime.publisher.subscriber_count() == 0

    # Reconnecting gives a fresh snapshot.
    with client.websocket_connect(ENDPOINT) as ws:
        ws.send_json(HELLO)
        assert ws.receive_json() == SNAPSHOT_EMPTY


# --- AC-10: maximum of connections ---------------------------------------------------------------


@pytest.mark.spec("realtime_events.AC-10")
def test_closes_new_connections_with_1013_beyond_the_maximum(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    snapshots = RecordingSnapshots()
    app, realtime = _build(settings, snapshots=snapshots, ws_max_connections=2)
    client = client_for(app)
    with client.websocket_connect(ENDPOINT) as first, client.websocket_connect(ENDPOINT):
        # The second one counts while it waits for its hello.
        first.send_json(HELLO)
        assert first.receive_json() == SNAPSHOT_EMPTY
        with client.websocket_connect(ENDPOINT) as third:
            third.send_json({"type": "hello", "device_id": OTHER_DEVICE})
            assert third.receive() == {"type": "websocket.close", "code": 1013, "reason": ""}
        assert snapshots.calls == [_device_hash(settings)]  # the third hello was not processed
    wait_until_closed(client, realtime.registry)

    with client.websocket_connect(ENDPOINT) as again:
        again.send_json(HELLO)
        assert again.receive_json() == SNAPSHOT_EMPTY


def test_default_limits_come_from_the_settings(settings: Settings) -> None:
    assert (
        settings.ws_max_connections,
        settings.ws_ping_interval_s,
        settings.ws_hello_timeout_s,
        settings.event_queue_size,
    ) == (500, 25, 5, 100)


# --- AC-03: no orphan subscriptions --------------------------------------------------------------


@pytest.mark.spec("realtime_events.AC-03")
def test_closing_the_socket_removes_its_subscription(
    settings: Settings, client_for: Callable[[FastAPI], TestClient]
) -> None:
    app, realtime = _build(settings)
    client = client_for(app)
    with client.websocket_connect(ENDPOINT) as ws, client.websocket_connect(ENDPOINT) as ws2:
        ws.send_json(HELLO)
        ws2.send_json(HELLO)  # same device, two tabs
        assert ws.receive_json() == SNAPSHOT_EMPTY
        assert ws2.receive_json() == SNAPSHOT_EMPTY
        assert realtime.publisher.subscriber_count() == 2
        ws.close(1000)
        ws2.close(1001)
        wait_until_closed(client, realtime.registry)
        assert realtime.publisher.subscriber_count() == 0
        assert realtime.registry.open_connections == 0


# --- AC-11: application stop ---------------------------------------------------------------------


@pytest.mark.spec("realtime_events.AC-11")
def test_closes_open_connections_with_1001_when_the_application_stops(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, realtime = _build(settings)
    with TestClient(app) as client:
        connected = client.websocket_connect(ENDPOINT).__enter__()
        waiting_hello = client.websocket_connect(ENDPOINT).__enter__()
        connected.send_json(HELLO)
        assert connected.receive_json() == SNAPSHOT_EMPTY

        # Stop the application (lifespan shutdown) while both sockets are open.
        assert client.portal is not None
        client.portal.call(client.wait_shutdown)

        assert connected.receive() == {"type": "websocket.close", "code": 1001, "reason": ""}
        assert waiting_hello.receive() == {"type": "websocket.close", "code": 1001, "reason": ""}
        assert realtime.registry.open_connections == 0
        assert realtime.publisher.subscriber_count() == 0
        connected.__exit__(None, None, None)
        waiting_hello.__exit__(None, None, None)

        async def already_stopped() -> None:
            return None

        monkeypatch.setattr(client, "wait_shutdown", already_stopped)
