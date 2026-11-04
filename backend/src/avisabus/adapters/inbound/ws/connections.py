"""Open WebSocket connections (realtime_events design §2): maximum, shutdown and `ws.stats`.

The registry counts every accepted socket, also while it waits for its `hello` (AC-10), logs the
life of each one without any device field (AC-13) and, when the application stops, asks every
connection to close with `1001` and waits for them (AC-11).
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta
from typing import Any, Protocol

from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.events import EventPublisher

DEFAULT_MAX_CONNECTIONS = 500
WS_STATS_INTERVAL = timedelta(minutes=5)
CLOSE_TIMEOUT_S = 5.0
"""Longest wait, at shutdown, for the connections to send their close frame."""

TRY_AGAIN_LATER = 1013


class Logger(Protocol):
    """Structured logger (structlog's bound logger in production)."""

    def info(self, event: str, **fields: Any) -> Any: ...


class Connection:
    """One accepted socket. `stopping` is set when the application stops; the endpoint closes
    the socket and calls `ConnectionRegistry.close`, which sets `finished`."""

    __slots__ = ("connected", "endpoint", "finished", "opened_at", "stopping")

    def __init__(self, endpoint: str, opened_at: datetime) -> None:
        self.endpoint = endpoint
        self.opened_at = opened_at
        self.connected = False
        self.stopping = asyncio.Event()
        self.finished = asyncio.Event()


class ConnectionRegistry:
    def __init__(
        self,
        *,
        max_connections: int = DEFAULT_MAX_CONNECTIONS,
        clock: Clock,
        publisher: EventPublisher,
        logger: Logger,
        stats_interval: timedelta = WS_STATS_INTERVAL,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if max_connections < 1:
            raise ValueError("max_connections must be at least 1")
        self._max = max_connections
        self._clock = clock
        self._publisher = publisher
        self._logger = logger
        self._stats_interval = stats_interval
        self._sleep = sleep
        self._open: set[Connection] = set()

    @property
    def open_connections(self) -> int:
        return len(self._open)

    def open(self, endpoint: str) -> Connection | None:
        """Register an accepted socket; `None` (and `ws.rejected` 1013) when the maximum is
        reached (AC-10)."""
        if len(self._open) >= self._max:
            self._logger.info("ws.rejected", endpoint=endpoint, code=TRY_AGAIN_LATER)
            return None
        connection = Connection(endpoint, self._clock.now())
        self._open.add(connection)
        return connection

    def connected(self, connection: Connection) -> None:
        """The `hello` was valid and the connection is subscribed."""
        connection.connected = True
        self._logger.info("ws.connected", endpoint=connection.endpoint)

    def reject(self, connection: Connection, code: int) -> None:
        """The `hello` was missing or invalid (`4408`, `4400`)."""
        if self._release(connection):
            self._logger.info("ws.rejected", endpoint=connection.endpoint, code=code)

    def close(self, connection: Connection, code: int) -> None:
        """The socket is closed, by either side. Idempotent."""
        if self._release(connection):
            duration = (self._clock.now() - connection.opened_at).total_seconds()
            self._logger.info(
                "ws.closed",
                endpoint=connection.endpoint,
                code=code,
                duration_s=round(duration, 3),
            )

    async def close_all(self) -> None:
        """Ask every open connection to close (with `1001`) and wait for them (AC-11)."""
        connections = list(self._open)
        if not connections:
            return
        for connection in connections:
            connection.stopping.set()
        waits = [asyncio.ensure_future(connection.finished.wait()) for connection in connections]
        _done, pending = await asyncio.wait(waits, timeout=CLOSE_TIMEOUT_S)
        for wait in pending:
            wait.cancel()

    def emit_stats(self) -> None:
        self._logger.info(
            "ws.stats",
            open_connections=len(self._open),
            subscriptions=self._publisher.subscriber_count(),
        )

    async def run_stats(self) -> None:
        """Every `stats_interval`, log `ws.stats`; runs until cancelled (AC-13)."""
        while True:
            await self._sleep(self._stats_interval.total_seconds())
            self.emit_stats()

    @asynccontextmanager
    async def running(self) -> AsyncIterator[None]:
        """For the application's lifespan: `ws.stats` while running; every connection closed
        on exit."""
        stats = asyncio.create_task(self.run_stats(), name="ws.stats")
        try:
            yield
        finally:
            await self.close_all()
            stats.cancel()
            with suppress(asyncio.CancelledError):
                await stats

    def _release(self, connection: Connection) -> bool:
        if connection not in self._open:
            return False
        self._open.discard(connection)
        connection.finished.set()
        return True
