"""Registry of open WebSocket connections (realtime_events T-04): limit, logs and shutdown."""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from avisabus.adapters.inbound.ws.connections import ConnectionRegistry
from avisabus.adapters.outbound.events.in_memory import InMemoryEventPublisher
from tests.support.fake_clock import FakeClock

ENDPOINT = "/ws/passenger"
NOW = datetime(2026, 11, 4, 8, 0, tzinfo=UTC)


@dataclass
class FakeLogger:
    events: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)

    def info(self, event: str, **fields: Any) -> None:
        self.events.append(("info", event, fields))

    def warning(self, event: str, **fields: Any) -> None:
        self.events.append(("warning", event, fields))

    def error(self, event: str, **fields: Any) -> None:
        self.events.append(("error", event, fields))

    def named(self, event: str) -> list[dict[str, Any]]:
        return [fields for _, name, fields in self.events if name == event]


@dataclass
class World:
    clock: FakeClock
    logger: FakeLogger
    publisher: InMemoryEventPublisher
    registry: ConnectionRegistry


def _world(max_connections: int = 500, **kwargs: Any) -> World:
    clock, logger, publisher = FakeClock(NOW), FakeLogger(), InMemoryEventPublisher()
    registry = ConnectionRegistry(
        max_connections=max_connections,
        clock=clock,
        publisher=publisher,
        logger=logger,
        **kwargs,
    )
    return World(clock, logger, publisher, registry)


@pytest.mark.spec("realtime_events.AC-13")
def test_logs_connected_and_closed_with_code_and_duration() -> None:
    world = _world()
    connection = world.registry.open(ENDPOINT)
    assert connection is not None
    world.clock.advance(timedelta(seconds=1.5))
    world.registry.connected(connection)
    world.clock.advance(timedelta(minutes=2))
    world.registry.close(connection, 1000)

    assert world.logger.events == [
        ("info", "ws.connected", {"endpoint": ENDPOINT}),
        ("info", "ws.closed", {"endpoint": ENDPOINT, "code": 1000, "duration_s": 121.5}),
    ]


@pytest.mark.spec("realtime_events.AC-13")
@pytest.mark.parametrize("code", [4400, 4408])
def test_logs_a_rejected_hello_with_its_code(code: int) -> None:
    world = _world()
    connection = world.registry.open(ENDPOINT)
    assert connection is not None
    world.registry.reject(connection, code)
    assert world.logger.events == [("info", "ws.rejected", {"endpoint": ENDPOINT, "code": code})]
    assert world.registry.open_connections == 0


@pytest.mark.spec("realtime_events.AC-10")
@pytest.mark.spec("realtime_events.AC-13")
def test_rejects_new_connections_beyond_the_maximum() -> None:
    world = _world(max_connections=2)
    first, second = world.registry.open(ENDPOINT), world.registry.open(ENDPOINT)
    assert first is not None
    assert second is not None
    assert world.registry.open(ENDPOINT) is None
    assert world.logger.named("ws.rejected") == [{"endpoint": ENDPOINT, "code": 1013}]
    assert world.registry.open_connections == 2

    world.registry.close(first, 1000)
    assert world.registry.open(ENDPOINT) is not None  # the slot is free again


@pytest.mark.spec("realtime_events.AC-10")
def test_default_maximum_is_500() -> None:
    world = _world()
    connections = [world.registry.open(ENDPOINT) for _ in range(500)]
    assert all(connection is not None for connection in connections)
    assert world.registry.open(ENDPOINT) is None


@pytest.mark.spec("realtime_events.AC-13")
def test_closing_twice_logs_once() -> None:
    world = _world()
    connection = world.registry.open(ENDPOINT)
    assert connection is not None
    world.registry.close(connection, 1000)
    world.registry.close(connection, 1011)
    assert len(world.logger.named("ws.closed")) == 1


@pytest.mark.spec("realtime_events.AC-13")
def test_logs_never_carry_device_fields() -> None:
    world = _world()
    connection = world.registry.open(ENDPOINT)
    assert connection is not None
    world.registry.connected(connection)
    world.registry.close(connection, 4429)
    world.registry.emit_stats()
    for _, _, fields in world.logger.events:
        assert not {"device_id", "device_hash", "channel"} & fields.keys()


@pytest.mark.spec("realtime_events.AC-13")
def test_stats_report_open_connections_and_subscriptions() -> None:
    world = _world()
    world.registry.open(ENDPOINT)
    world.registry.open(ENDPOINT)
    world.publisher.subscribe("device:a")
    world.registry.emit_stats()
    assert world.logger.named("ws.stats") == [{"open_connections": 2, "subscriptions": 1}]


@pytest.mark.spec("realtime_events.AC-13")
async def test_stats_are_logged_every_5_minutes_while_running() -> None:
    sleeps: list[float] = []

    async def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) > 3:
            await asyncio.Event().wait()  # never again: the test stops here

    world = _world(sleep=sleep)
    connection = world.registry.open(ENDPOINT)
    assert connection is not None
    async with world.registry.running():
        for _ in range(5):
            await asyncio.sleep(0)
        world.registry.close(connection, 1000)
    assert sleeps == [300, 300, 300, 300]
    assert world.logger.named("ws.stats") == [{"open_connections": 1, "subscriptions": 0}] * 3


@pytest.mark.spec("realtime_events.AC-11")
async def test_close_all_asks_every_connection_to_stop_and_waits_for_them() -> None:
    world = _world()
    first, second = world.registry.open(ENDPOINT), world.registry.open(ENDPOINT)
    assert first is not None
    assert second is not None
    world.registry.connected(first)
    closed: list[int] = []

    async def serve(connection: Any) -> None:
        await connection.stopping.wait()
        closed.append(1001)
        world.registry.close(connection, 1001)

    tasks = [asyncio.ensure_future(serve(c)) for c in (first, second)]
    await asyncio.sleep(0)
    assert not first.stopping.is_set()
    await world.registry.close_all()
    assert closed == [1001, 1001]
    assert world.registry.open_connections == 0
    assert [f["code"] for f in world.logger.named("ws.closed")] == [1001, 1001]
    await asyncio.gather(*tasks)


@pytest.mark.spec("realtime_events.AC-11")
async def test_running_closes_every_connection_on_exit() -> None:
    world = _world()
    connection = world.registry.open(ENDPOINT)
    assert connection is not None

    async def serve() -> None:
        await connection.stopping.wait()
        world.registry.close(connection, 1001)

    task = asyncio.ensure_future(serve())
    async with world.registry.running():
        await asyncio.sleep(0)
        assert not connection.stopping.is_set()
    assert connection.stopping.is_set()
    assert world.registry.open_connections == 0
    await task


@pytest.mark.parametrize("maximum", [0, -1])
def test_maximum_must_be_positive(maximum: int) -> None:
    with pytest.raises(ValueError, match="max_connections"):
        _world(max_connections=maximum)
