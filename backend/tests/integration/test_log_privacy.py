"""No unhandled exception reaches the logs with its message (H-01, realtime_events AC-12).

Logs are captured as the JSON lines that the process writes to stdout. The HTTP request is served
by uvicorn's own HTTP protocol (`H11Protocol`) over an in-memory transport, so the line that
uvicorn writes when the application re-raises the exception ("Exception in ASGI application") is
captured too. No socket is opened.
"""

import asyncio
import json
import logging
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from fastapi import FastAPI
from starlette.testclient import TestClient
from uvicorn.config import Config
from uvicorn.protocols.http.h11_impl import H11Protocol
from uvicorn.server import ServerState

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import build_realtime
from avisabus.adapters.outbound.security.hmac_device_hasher import HmacDeviceHasher
from avisabus.config import Settings
from avisabus.domain.models.device import parse_device_id
from avisabus.domain.models.events import Event
from avisabus.domain.ports.events import device_channel
from avisabus.logging import configure_logging
from tests.conftest import DEFAULT_NOW
from tests.support.fake_clock import FakeClock
from tests.support.ws import FakeSleep, wait_until_closed

DEVICE = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


@pytest.fixture
def marker() -> str:
    """A message that would identify a device if it reached the logs."""
    return f"MARKER-{uuid.uuid4().hex}-{DEVICE}"


def _records(out: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.splitlines() if line.strip()]


class _MemoryTransport(asyncio.Transport):
    """The socket side of a connection, kept in memory."""

    def __init__(self) -> None:
        super().__init__()
        self.written = bytearray()
        self.closed = False

    def get_extra_info(self, name: str, default: Any = None) -> Any:
        return {"sockname": ("127.0.0.1", 8000), "peername": ("127.0.0.1", 50000)}.get(
            name, default
        )

    def write(self, data: bytes | bytearray | memoryview) -> None:
        self.written.extend(data)

    def close(self) -> None:
        self.closed = True

    def is_closing(self) -> bool:
        return self.closed

    def pause_reading(self) -> None:
        pass

    def resume_reading(self) -> None:
        pass


async def _serve_with_uvicorn(app: FastAPI, request: bytes) -> bytes:
    """One HTTP/1.1 request through uvicorn's h11 protocol; returns the raw response."""
    config = Config(app=app, http="h11", lifespan="off", log_config=None, access_log=False)
    state = ServerState()
    protocol = H11Protocol(config=config, server_state=state, app_state={})
    transport = _MemoryTransport()
    protocol.connection_made(transport)
    protocol.data_received(request)
    await asyncio.gather(*list(state.tasks))
    protocol.connection_lost(None)
    return bytes(transport.written)


def _app_with_failing_route(settings: Settings, marker: str) -> FastAPI:
    """The route that raises exists only in this test, never in the application."""
    app = create_app(settings)

    @app.get("/api/v1/test-only/boom")
    async def boom() -> None:
        raise RuntimeError(marker)

    return app


@pytest.mark.spec("realtime_events.AC-12")
async def test_http_unhandled_exception_logs_only_its_type(
    settings: Settings, marker: str, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    app = _app_with_failing_route(settings, marker)

    response = await _serve_with_uvicorn(
        app, b"GET /api/v1/test-only/boom HTTP/1.1\r\nHost: testserver\r\n\r\n"
    )

    assert response.startswith(b"HTTP/1.1 500 ")
    assert marker.encode() not in response
    out = capsys.readouterr().out
    assert marker not in out
    assert DEVICE not in out
    assert "Traceback" not in out
    records = _records(out)
    # Ours, from the exception handler, and uvicorn's, when Starlette re-raises the exception.
    handler = [r for r in records if r["logger"] == "avisabus.adapters.inbound.http.errors"]
    assert handler == [
        {
            "event": "unhandled_exception",
            "error_type": "RuntimeError",
            "method": "GET",
            "level": "error",
            "logger": "avisabus.adapters.inbound.http.errors",
            "timestamp": handler[0]["timestamp"],
        }
    ]
    uvicorn_lines = [r for r in records if r["logger"] == "uvicorn.error"]
    assert len(uvicorn_lines) == 1
    assert uvicorn_lines[0]["event"] == "unhandled_exception"
    assert uvicorn_lines[0]["error_type"] == "RuntimeError"
    assert {r["event"] for r in records} == {"unhandled_exception"}
    for record in records:
        assert not {"exception", "exc_info", "exc_text", "stack", "stack_info"} & record.keys()


@pytest.mark.spec("realtime_events.AC-12")
def test_structlog_exception_logs_keep_only_the_type(
    marker: str, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    log = structlog.get_logger("avisabus.tests")
    try:
        raise ValueError(marker)
    except ValueError:
        log.exception("something_failed", stop_id="508")
    try:
        raise KeyError(marker)
    except KeyError as error:
        log.error("lookup_failed", exc_info=error)
        log.warning("with_stack", exc_info=True, stack_info=True)

    out = capsys.readouterr().out
    assert marker not in out
    assert "Traceback" not in out
    records = _records(out)
    assert [(r["event"], r["error_type"]) for r in records] == [
        ("something_failed", "ValueError"),
        ("lookup_failed", "KeyError"),
        ("with_stack", "KeyError"),
    ]
    assert records[0]["stop_id"] == "508"
    for record in records:
        assert not {"exception", "exc_info", "stack", "stack_info"} & record.keys()


@pytest.mark.spec("realtime_events.AC-12")
def test_standard_library_exception_logs_drop_message_and_traceback(
    marker: str, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    try:
        try:
            raise OSError(marker)
        except OSError as cause:
            raise RuntimeError("wrapped") from cause
    except RuntimeError:
        # A third-party message may itself be built from the exception.
        logging.getLogger("uvicorn.error").exception("failed: %s", marker)
        logging.getLogger("asyncio").error("Task exception", exc_info=True, stack_info=True)

    out = capsys.readouterr().out
    assert marker not in out
    assert "Traceback" not in out
    assert "wrapped" not in out
    records = _records(out)
    assert [(r["logger"], r["event"], r["error_type"]) for r in records] == [
        ("uvicorn.error", "unhandled_exception", "RuntimeError"),
        ("asyncio", "unhandled_exception", "RuntimeError"),
    ]


@pytest.mark.spec("realtime_events.AC-12")
def test_logs_without_exception_are_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logging.getLogger("uvicorn.error").info("Started server process [%d]", 42)
    structlog.get_logger("avisabus.tests").info("ws.connected", endpoint="/ws/passenger")
    records = _records(capsys.readouterr().out)
    assert [r["event"] for r in records] == ["Started server process [42]", "ws.connected"]
    assert all("error_type" not in r for r in records)


class _FailingSnapshots:
    def __init__(self, marker: str) -> None:
        self.marker = marker

    async def active_alerts(self, device_hash: str) -> list[Any]:
        raise RuntimeError(self.marker)


@pytest.mark.spec("realtime_events.AC-12")
def test_websocket_unhandled_exception_logs_only_its_type_and_closes_with_1011(
    settings: Settings, marker: str, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    realtime = build_realtime(
        settings, FakeClock(DEFAULT_NOW), snapshots=_FailingSnapshots(marker), sleep=FakeSleep()
    )
    app = create_app(settings, realtime=realtime)
    with TestClient(app) as client, client.websocket_connect("/ws/passenger") as ws:
        ws.send_json({"type": "hello", "device_id": DEVICE})
        assert ws.receive() == {"type": "websocket.close", "code": 1011, "reason": ""}

    out = capsys.readouterr().out
    assert marker not in out
    assert DEVICE not in out
    assert "Traceback" not in out
    records = _records(out)
    failures = [r for r in records if r["event"] == "unhandled_exception"]
    assert [(r["error_type"], r["endpoint"]) for r in failures] == [
        ("RuntimeError", "/ws/passenger")
    ]
    closed = [r for r in records if r["event"] == "ws.closed"]
    assert [r["code"] for r in closed] == [1011]
    for record in records:
        assert not {"exception", "exc_info", "stack"} & record.keys()


@pytest.mark.spec("realtime_events.AC-05")
@pytest.mark.spec("realtime_events.AC-13")
def test_a_complete_websocket_session_never_logs_the_device(
    settings: Settings, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("DEBUG")
    realtime = build_realtime(settings, FakeClock(DEFAULT_NOW), sleep=FakeSleep())
    app = create_app(settings, realtime=realtime)
    device_hash = HmacDeviceHasher(settings.stop_token_secret_bytes()).hash(parse_device_id(DEVICE))
    with TestClient(app) as client:
        with client.websocket_connect("/ws/passenger") as ws:
            ws.send_json({"type": "hello", "device_id": DEVICE})
            assert ws.receive_json() == {"type": "alerts.snapshot", "alerts": []}
            assert client.portal is not None
            client.portal.call(
                realtime.publisher.publish,
                device_channel(device_hash),
                Event(type="alert.test", payload={"n": 1}),
            )
            assert ws.receive_json() == {"type": "alert.test", "n": 1}
            ws.send_json({"type": "pong"})
            ws.close(1000)
            wait_until_closed(client, realtime.registry)
        with client.websocket_connect("/ws/passenger") as invalid:
            invalid.send_json({"type": "hello", "device_id": DEVICE.upper()})
            assert invalid.receive()["code"] == 4400

    out = capsys.readouterr().out
    assert DEVICE not in out
    assert DEVICE.upper() not in out
    assert device_hash not in out
    events = [r["event"] for r in _records(out)]
    assert events.count("ws.connected") == 1
    assert events.count("ws.closed") == 1
    assert events.count("ws.rejected") == 1
    for record in _records(out):
        assert not {"device_id", "device_hash", "channel"} & record.keys()
