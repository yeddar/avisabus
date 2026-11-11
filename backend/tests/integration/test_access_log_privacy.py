"""No access log line carries the client address nor a query string (deployment_rpi AC-09).

The application is served by a real uvicorn server on the loopback interface, configured as in the
production image (`--proxy-headers --forwarded-allow-ips '*'`), and the requests carry the
`X-Forwarded-For` that the `web` container sets: uvicorn then logs that address as the client.
The JSON lines written to stdout are captured. Only `127.0.0.1` is reachable (`allow_hosts`).
"""

import asyncio
import json
import logging
import socket
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import structlog
import uvicorn
from fastapi import FastAPI
from websockets.asyncio.client import connect

from avisabus.adapters.inbound.http.access_log import (
    ACCESS_LOGGER,
    SERVER_LOGGER,
    ClientAddressFilter,
    SocketAddressFilter,
)
from avisabus.logging import configure_logging
from tests.support.alerts_app import DEVICE, build_alerts_app
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import STOP_508_PEAK
from tests.support.stops import import_feed, new_engine, replay, token

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
CLIENT_IP = "203.0.113.7"
LOOPBACK = "127.0.0.1"
QUERY_MARKER = "q-marker-5f1c"
STARTUP_TIMEOUT_S = 10
CLIENT_LOGGERS = ("httpx", "httpcore", "websockets")
"""Loggers of the test's own clients, which do log the URL they request."""


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    engine = new_engine(tmp_path / "avisabus.sqlite")
    import_feed(engine, GTFS_MINI)
    clock = FakeClock(PEAK_START)
    source, _ = replay(STOP_508_PEAK, clock)
    return build_alerts_app(engine, clock, source).app


class _Server(uvicorn.Server):
    """Signals when it is listening, so the test waits for an event instead of polling."""

    def __init__(self, config: uvicorn.Config) -> None:
        super().__init__(config)
        self.listening = asyncio.Event()

    async def startup(self, sockets: list[socket.socket] | None = None) -> None:
        await super().startup(sockets)
        self.listening.set()


@asynccontextmanager
async def _served(app: FastAPI) -> AsyncIterator[int]:
    """A real uvicorn server, as in the production image, on an ephemeral loopback port."""
    config = uvicorn.Config(
        app,
        host=LOOPBACK,
        port=0,
        proxy_headers=True,
        forwarded_allow_ips="*",
        server_header=False,
        log_config=None,  # the process logging is ours (`configure_logging`), as in `main.py`
        lifespan="on",
    )
    server = _Server(config)
    task = asyncio.create_task(server.serve())
    listening = asyncio.create_task(server.listening.wait())
    try:
        await asyncio.wait(
            {task, listening}, timeout=STARTUP_TIMEOUT_S, return_when="FIRST_COMPLETED"
        )
        assert server.started, "uvicorn did not start"
        yield server.servers[0].sockets[0].getsockname()[1]
    finally:
        listening.cancel()
        server.should_exit = True
        await task


def _records(out: str) -> list[dict[str, Any]]:
    return [json.loads(line) for line in out.splitlines() if line.strip()]


@pytest.mark.spec("deployment_rpi.AC-09")
@pytest.mark.enable_socket
@pytest.mark.allow_hosts([LOOPBACK])
async def test_access_logs_carry_neither_the_client_address_nor_the_query(
    app: FastAPI, capsys: pytest.CaptureFixture[str]
) -> None:
    configure_logging("INFO")
    stop_token = token("508")
    forwarded = {"X-Forwarded-For": CLIENT_IP}
    async with _served(app) as port:
        base = f"http://{LOOPBACK}:{port}"
        async with httpx.AsyncClient(base_url=base, headers=forwarded, trust_env=False) as http:
            health = await http.get("/api/v1/health")
            stop = await http.get("/api/v1/stops/508", params={"t": stop_token})
            arrivals = await http.get("/api/v1/stops/508/arrivals", params={"t": stop_token})
            alert = await http.post(
                "/api/v1/alerts",
                params={"debug": QUERY_MARKER},
                json={"stop_id": "508", "token": stop_token},
                headers={"X-Device-Id": DEVICE},
            )
            mine = await http.get("/api/v1/alerts/mine", headers={"X-Device-Id": DEVICE})
            spa = await http.get("/p/508", params={"t": stop_token})  # not a backend route
        async with connect(
            f"ws://{LOOPBACK}:{port}/ws/passenger?probe={QUERY_MARKER}",
            additional_headers=forwarded,
        ) as ws:
            await ws.send(json.dumps({"type": "hello", "device_id": DEVICE}))
            snapshot = json.loads(await ws.recv())

    assert health.status_code == 200
    assert stop.status_code == 200
    assert arrivals.status_code == 200
    assert alert.status_code == 422
    assert mine.status_code == 200
    assert spa.status_code == 404
    assert snapshot == {"type": "alerts.snapshot", "alerts": []}

    records = [
        r for r in _records(capsys.readouterr().out) if not r["logger"].startswith(CLIENT_LOGGERS)
    ]
    out = json.dumps(records)
    access = [r["event"] for r in records if r["logger"] == ACCESS_LOGGER]
    sockets = [r["event"] for r in records if "WebSocket" in r["event"]]
    # Every request is in the access log, without address and without query string.
    assert access == [
        '- - "GET /api/v1/health HTTP/1.1" 200',
        '- - "GET /api/v1/stops/508 HTTP/1.1" 200',
        '- - "GET /api/v1/stops/508/arrivals HTTP/1.1" 200',
        '- - "POST /api/v1/alerts HTTP/1.1" 422',
        '- - "GET /api/v1/alerts/mine HTTP/1.1" 200',
        '- - "GET /p/508 HTTP/1.1" 404',
    ]
    assert sockets == ['- - "WebSocket /ws/passenger" [accepted]']
    for line in [*access, *sockets]:
        assert LOOPBACK not in line
    # Nowhere in the server's output: neither the real address nor the QR token nor any query.
    assert CLIENT_IP not in out
    assert stop_token not in out
    assert QUERY_MARKER not in out
    assert DEVICE not in out


@pytest.mark.spec("deployment_rpi.AC-09")
@pytest.mark.parametrize(
    ("args", "expected"),
    [
        (
            ("203.0.113.7:50000", "GET", "/api/v1/stops/508?t=abc", "1.1", 200),
            '- - "GET /api/v1/stops/508 HTTP/1.1" 200',
        ),
        (
            ("203.0.113.7:50000", "POST", "/api/v1/driver/sessions", "1.1", 201),
            '- - "POST /api/v1/driver/sessions HTTP/1.1" 201',
        ),
        (("", "GET", "/api/v1/health", "1.1", 200), '- - "GET /api/v1/health HTTP/1.1" 200'),
    ],
)
def test_the_access_filter_masks_every_path(args: tuple[object, ...], expected: str) -> None:
    record = logging.LogRecord(
        ACCESS_LOGGER, logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', args, None
    )
    assert ClientAddressFilter().filter(record)
    assert record.getMessage() == expected


@pytest.mark.spec("deployment_rpi.AC-09")
@pytest.mark.parametrize(
    ("message", "args", "expected"),
    [
        (
            '%s - "WebSocket %s" [accepted]',
            ("203.0.113.7:50000", "/ws/passenger?x=1"),
            '- - "WebSocket /ws/passenger" [accepted]',
        ),
        (
            '%s - "WebSocket %s" 403',
            ("203.0.113.7:1", "/ws/driver"),
            '- - "WebSocket /ws/driver" 403',
        ),
        (
            '%s - "WebSocket %s" %d',
            ("203.0.113.7:1", "/ws/other?t=abc", 500),
            '- - "WebSocket /ws/other" 500',
        ),
        ("Started server process [%d]", (12,), "Started server process [12]"),
    ],
)
def test_the_socket_filter_masks_every_socket_and_leaves_other_lines(
    message: str, args: tuple[object, ...], expected: str
) -> None:
    record = logging.LogRecord(SERVER_LOGGER, logging.INFO, __file__, 1, message, args, None)
    assert SocketAddressFilter().filter(record)
    assert record.getMessage() == expected
