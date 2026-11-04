"""Passenger WebSocket `/ws/passenger` (realtime_events design §3).

Protocol: the client sends `{"type": "hello", "device_id": "<uuid v4>"}` within the hello timeout
(else `4408`; `4400` if invalid); the server subscribes to `device:<device_hash>`, sends
`{"type": "alerts.snapshot", "alerts": [...]}` and then forwards the channel's events in order,
with `{"type": "ping"}` every ping interval. Client messages after the hello are ignored.

Close codes: `1000` normal, `1001` server stopping, `1011` unexpected error, `1013` too many
connections, `4400` invalid hello, `4408` no hello, `4429` subscription overflowed.

Privacy (RNF-06): neither the `device_id` nor its hash is ever logged.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState

from avisabus.adapters.inbound.ws.connections import (
    TRY_AGAIN_LATER,
    Connection,
    ConnectionRegistry,
)
from avisabus.domain.errors import InvalidDeviceIdError, SubscriptionOverflowError
from avisabus.domain.models.device import parse_device_id
from avisabus.domain.ports.device import DeviceHasher
from avisabus.domain.ports.events import EventPublisher, Subscription, device_channel

PASSENGER_ENDPOINT = "/ws/passenger"

NORMAL = 1000
GOING_AWAY = 1001
"""The server stops (AC-11)."""
ABNORMAL = 1006
"""Logged when the connection ends without a known close code (e.g. the task is cancelled)."""
INTERNAL_ERROR = 1011
INVALID_HELLO = 4400
HELLO_TIMEOUT = 4408
OVERFLOWED = 4429

PING = {"type": "ping"}

router = APIRouter()


class PassengerSnapshotProvider(Protocol):
    async def active_alerts(self, device_hash: str) -> list[Mapping[str, object]]:
        """Active alerts of the device, as sent in `alerts.snapshot`."""
        ...


class EmptySnapshotProvider:
    """No alerts yet: `alert_create` replaces it with the real provider."""

    async def active_alerts(self, device_hash: str) -> list[Mapping[str, object]]:
        return []


class Logger(Protocol):
    def error(self, event: str, **fields: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class PassengerSocket:
    """What `/ws/passenger` needs; `create_app` keeps it in `app.state.passenger_socket`."""

    publisher: EventPublisher
    hasher: DeviceHasher
    snapshots: PassengerSnapshotProvider
    registry: ConnectionRegistry
    logger: Logger
    hello_timeout_s: float
    ping_interval_s: float
    sleep: Callable[[float], Awaitable[None]] = field(default=asyncio.sleep)


class _Closed(Exception):  # noqa: N818 - control flow, not an error
    """The socket is already closed (by the client or the server) with `code`."""

    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


@router.websocket(PASSENGER_ENDPOINT)
async def passenger_socket(websocket: WebSocket) -> None:
    socket: PassengerSocket = websocket.app.state.passenger_socket
    await websocket.accept()
    connection = socket.registry.open(PASSENGER_ENDPOINT)
    if connection is None:  # AC-10: the hello is not even read
        await _close(websocket, TRY_AGAIN_LATER)
        return
    code = ABNORMAL
    try:
        code = await _serve(websocket, socket, connection)
    except _Closed as closed:
        code = closed.code
    except Exception as error:
        # Only the type: the message could carry an identifier (AC-12).
        socket.logger.error(
            "unhandled_exception", error_type=type(error).__name__, endpoint=PASSENGER_ENDPOINT
        )
        code = INTERNAL_ERROR
        await _close(websocket, INTERNAL_ERROR)
    finally:
        if code in (INVALID_HELLO, HELLO_TIMEOUT):
            socket.registry.reject(connection, code)
        else:
            socket.registry.close(connection, code)


async def _serve(websocket: WebSocket, socket: PassengerSocket, connection: Connection) -> int:
    """Run the protocol until the socket closes; return the close code."""
    text = await _first_message(websocket, socket, connection)
    try:
        device_id = parse_device_id(_hello_device_id(text))
    except InvalidDeviceIdError:
        return await _close(websocket, INVALID_HELLO)

    device_hash = socket.hasher.hash(device_id)
    subscription = socket.publisher.subscribe(device_channel(device_hash))  # before the snapshot
    try:
        socket.registry.connected(connection)
        alerts = await _until_stopping(
            socket.snapshots.active_alerts(device_hash), connection, websocket
        )
        await _send(websocket, {"type": "alerts.snapshot", "alerts": [dict(a) for a in alerts]})
        return await _forward(websocket, socket, connection, subscription)
    finally:
        subscription.close()  # AC-03


async def _first_message(
    websocket: WebSocket, socket: PassengerSocket, connection: Connection
) -> str | None:
    """Text of the first client message (`None` for a binary one). Closes with `4408` when the
    hello timeout elapses and with `1001` when the application stops."""
    receive = asyncio.ensure_future(websocket.receive())
    timeout = asyncio.ensure_future(socket.sleep(socket.hello_timeout_s))
    stopping = asyncio.ensure_future(connection.stopping.wait())
    try:
        done, _ = await asyncio.wait(
            {receive, timeout, stopping}, return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        await _cancel(receive, timeout, stopping)
    if receive in done:
        message = receive.result()
        if message["type"] == "websocket.disconnect":
            raise _Closed(message.get("code", NORMAL))
        text = message.get("text")
        return text if isinstance(text, str) else None
    if timeout in done:
        raise _Closed(await _close(websocket, HELLO_TIMEOUT))
    raise _Closed(await _close(websocket, GOING_AWAY))


def _hello_device_id(text: str | None) -> str | None:
    """`device_id` of a valid hello message; `None` when the message is not a hello."""
    if text is None:
        return None
    try:
        message = json.loads(text)
    except ValueError:
        return None
    if not isinstance(message, dict) or message.get("type") != "hello":
        return None
    device_id = message.get("device_id")
    return device_id if isinstance(device_id, str) else None


async def _until_stopping[T](
    awaitable: Awaitable[T], connection: Connection, websocket: WebSocket
) -> T:
    """Await `awaitable` unless the application stops first (then close with `1001`)."""
    work = asyncio.ensure_future(awaitable)
    stopping = asyncio.ensure_future(connection.stopping.wait())
    try:
        done, _ = await asyncio.wait({work, stopping}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await _cancel(work, stopping)
    if work in done:
        return work.result()
    raise _Closed(await _close(websocket, GOING_AWAY))


async def _forward(
    websocket: WebSocket,
    socket: PassengerSocket,
    connection: Connection,
    subscription: Subscription,
) -> int:
    """A reader (ignores messages, notices the client closing) and a writer (events, pings,
    server-side closes) run together; the first to finish stops the other."""
    reader = asyncio.ensure_future(_read_until_closed(websocket))
    writer = asyncio.ensure_future(_write(websocket, socket, connection, subscription))
    try:
        done, _ = await asyncio.wait({reader, writer}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        await _cancel(reader, writer)
    if reader in done:
        return reader.result()
    return await _close(websocket, writer.result())


async def _read_until_closed(websocket: WebSocket) -> int:
    """Ignore every client message (`pong` included, AC-08); return the client's close code."""
    while True:
        message = await websocket.receive()
        if message["type"] == "websocket.disconnect":
            code: int = message.get("code", NORMAL)
            return code


async def _write(
    websocket: WebSocket,
    socket: PassengerSocket,
    connection: Connection,
    subscription: Subscription,
) -> int:
    """Send events and pings until the server must close; return the close code to use."""
    next_event = asyncio.ensure_future(subscription.next_event())
    ping = asyncio.ensure_future(socket.sleep(socket.ping_interval_s))
    stopping = asyncio.ensure_future(connection.stopping.wait())
    try:
        while True:
            await asyncio.wait({next_event, ping, stopping}, return_when=asyncio.FIRST_COMPLETED)
            if next_event.done():
                try:
                    event = next_event.result()
                except SubscriptionOverflowError:
                    return OVERFLOWED  # AC-09
                await _send(websocket, event.message())
                next_event = asyncio.ensure_future(subscription.next_event())
            elif ping.done():
                ping.result()
                await _send(websocket, PING)
                ping = asyncio.ensure_future(socket.sleep(socket.ping_interval_s))
            else:
                return GOING_AWAY  # AC-11
    finally:
        await _cancel(next_event, ping, stopping)


async def _send(websocket: WebSocket, message: Mapping[str, Any]) -> None:
    try:
        await websocket.send_json(message)
    except WebSocketDisconnect as disconnect:
        raise _Closed(disconnect.code) from None


async def _close(websocket: WebSocket, code: int) -> int:
    """Close from the server side unless the socket is already closed; return `code`."""
    if (
        websocket.application_state != WebSocketState.DISCONNECTED
        and websocket.client_state != WebSocketState.DISCONNECTED
    ):
        # The client may have gone away meanwhile.
        with suppress(WebSocketDisconnect, RuntimeError, OSError):
            await websocket.close(code)
    return code


async def _cancel(*tasks: asyncio.Future[Any]) -> None:
    """Cancel the waits that did not finish and wait for them. Finished ones keep their result
    (or exception) for the caller. A cancellation of the caller itself still propagates."""
    pending = [task for task in tasks if not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.wait(pending)
    for task in pending:
        if not task.cancelled():
            task.exception()  # an abandoned wait has nothing left to report
