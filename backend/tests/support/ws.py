"""Helpers for the WebSocket tests: time never passes for real and the network is not used."""

import asyncio
import json
from collections.abc import Mapping
from typing import Any

import anyio
from starlette.testclient import TestClient, WebSocketTestSession
from starlette.types import Message

from avisabus.adapters.inbound.ws.connections import ConnectionRegistry

DEFAULT_TURNS = 1000


class FakeSleep:
    """`sleep` that returns at once the first `immediate[seconds]` times and then never."""

    def __init__(self, immediate: Mapping[float, int] | None = None) -> None:
        self.immediate = dict(immediate or {})
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)
        if self.immediate.get(seconds, 0) > 0:
            self.immediate[seconds] -= 1
            return
        await asyncio.Event().wait()


def wait_until_closed(client: TestClient, registry: ConnectionRegistry) -> None:
    """Let the application finish the connections that the client has just closed."""

    async def wait() -> None:
        for _ in range(1000):
            if registry.open_connections == 0:
                return
            await asyncio.sleep(0)
        raise AssertionError("the connections did not close")

    assert client.portal is not None
    client.portal.call(wait)


def receive_soon(ws: WebSocketTestSession, turns: int = DEFAULT_TURNS) -> Message:
    """`ws.receive()` that fails instead of hanging when no message comes: it lets the
    application's event loop run at most `turns` times (no real time) waiting for one.

    The limit is in loop turns, not seconds: the socket endpoint does all its work in the event
    loop (no threads) and the tests never let real time pass, so it does not depend on the load
    of the machine. This is the only place that uses Starlette's private `_send_rx`: there is no
    public receive with a limit.
    """

    async def receive() -> Message:
        for _ in range(turns):
            try:
                return ws._send_rx.receive_nowait()  # noqa: SLF001 - no public bounded receive
            except anyio.WouldBlock:
                await asyncio.sleep(0)
        raise AssertionError("the socket sent nothing")

    return ws.portal.call(receive)


def receive_json_soon(ws: WebSocketTestSession, turns: int = DEFAULT_TURNS) -> Any:
    """`ws.receive_json()` with the limit of `receive_soon`."""
    message = receive_soon(ws, turns)
    ws._raise_on_close(message)  # noqa: SLF001
    return json.loads(message["text"])
