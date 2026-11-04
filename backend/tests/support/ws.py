"""Helpers for the WebSocket tests: time never passes for real and the network is not used."""

import asyncio
from collections.abc import Mapping

from starlette.testclient import TestClient

from avisabus.adapters.inbound.ws.connections import ConnectionRegistry


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
