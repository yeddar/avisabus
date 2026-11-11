"""Driver WebSocket `/ws/driver` (driver_demand design §3, ADR-009).

Protocol, as in `/ws/passenger`: the client sends `{"type": "hello", "session_token": "…"}` within
the hello timeout (else `4408`; `4400` if it is not a hello, `4401` if the token is not of an open
shift); the server subscribes to `driver:<session_id>`, sends the current view and then every new
one, with `{"type": "ping"}` every ping interval. Client messages after the hello are ignored. When
the shift closes it sends `{"type": "session.closed", "reason": …}` and closes with `1000`.

Close codes: those of `/ws/passenger` plus `4401`.

Privacy: neither the token nor the `session_id` is ever logged (`ws.*` only carry the endpoint), and
an unexpected exception only logs its type.
"""

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from fastapi import APIRouter, WebSocket

from avisabus.adapters.inbound.ws.connections import (
    TRY_AGAIN_LATER,
    Connection,
    ConnectionRegistry,
)
from avisabus.adapters.inbound.ws.passenger import (
    ABNORMAL,
    GOING_AWAY,
    HELLO_TIMEOUT,
    INTERNAL_ERROR,
    INVALID_HELLO,
    NORMAL,
    OVERFLOWED,
    PING,
    _cancel,
    _close,
    _Closed,
    _read_until_closed,
    _send,
    _until_stopping,
)
from avisabus.application.build_driver_view import BuildDriverView
from avisabus.application.demand_views import SESSION_CLOSED, driver_channel, driver_view_event
from avisabus.application.driver_sessions import AuthenticateDriverSession
from avisabus.domain.errors import InvalidSessionError, SubscriptionOverflowError
from avisabus.domain.ports.events import EventPublisher, Subscription

DRIVER_ENDPOINT = "/ws/driver"
INVALID_TOKEN = 4401

router = APIRouter()


class Logger(Protocol):
    def error(self, event: str, **fields: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class DriverSocket:
    """What `/ws/driver` needs; `create_app` keeps it in `app.state.driver_socket`."""

    publisher: EventPublisher
    authenticate: AuthenticateDriverSession
    build: BuildDriverView
    registry: ConnectionRegistry
    logger: Logger
    hello_timeout_s: float
    ping_interval_s: float
    sleep: Callable[[float], Awaitable[None]] = field(default=asyncio.sleep)


@router.websocket(DRIVER_ENDPOINT)
async def driver_socket(websocket: WebSocket) -> None:
    socket: DriverSocket = websocket.app.state.driver_socket
    await websocket.accept()
    connection = socket.registry.open(DRIVER_ENDPOINT)
    if connection is None:  # the hello is not even read
        await _close(websocket, TRY_AGAIN_LATER)
        return
    code = ABNORMAL
    try:
        code = await _serve(websocket, socket, connection)
    except _Closed as closed:
        code = closed.code
    except Exception as error:
        # Only the type: the message could carry an identifier.
        socket.logger.error(
            "unhandled_exception", error_type=type(error).__name__, endpoint=DRIVER_ENDPOINT
        )
        code = INTERNAL_ERROR
        await _close(websocket, INTERNAL_ERROR)
    finally:
        if code in (INVALID_HELLO, HELLO_TIMEOUT, INVALID_TOKEN):
            socket.registry.reject(connection, code)
        else:
            socket.registry.close(connection, code)


async def _serve(websocket: WebSocket, socket: DriverSocket, connection: Connection) -> int:
    """Run the protocol until the socket closes; return the close code."""
    token = _hello_token(await _first_message(websocket, socket, connection))
    if token is None:
        return await _close(websocket, INVALID_HELLO)
    try:
        session = await socket.authenticate.execute(token)
    except (InvalidSessionError, UnicodeEncodeError):  # a lone surrogate cannot even be hashed
        return await _close(websocket, INVALID_TOKEN)

    subscription = socket.publisher.subscribe(driver_channel(session.session_id))  # before the view
    try:
        socket.registry.connected(connection)
        view = await _until_stopping(socket.build.execute(session), connection, websocket)
        await _send(websocket, driver_view_event(view).message())
        return await _forward(websocket, socket, connection, subscription)
    finally:
        subscription.close()


async def _first_message(
    websocket: WebSocket, socket: DriverSocket, connection: Connection
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


def _hello_token(text: str | None) -> str | None:
    """`session_token` of a valid hello message; `None` when the message is not a hello."""
    if text is None:
        return None
    try:
        message = json.loads(text)
    except ValueError:
        return None
    if not isinstance(message, dict) or message.get("type") != "hello":
        return None
    token = message.get("session_token")
    return token if isinstance(token, str) else None


async def _forward(
    websocket: WebSocket,
    socket: DriverSocket,
    connection: Connection,
    subscription: Subscription,
) -> int:
    """A reader (ignores messages, notices the client closing) and a writer (views, pings,
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


async def _write(
    websocket: WebSocket,
    socket: DriverSocket,
    connection: Connection,
    subscription: Subscription,
) -> int:
    """Send views and pings until the server must close; return the close code to use."""
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
                    return OVERFLOWED
                await _send(websocket, event.message())
                if event.type == SESSION_CLOSED:
                    return NORMAL
                next_event = asyncio.ensure_future(subscription.next_event())
            elif ping.done():
                ping.result()
                await _send(websocket, PING)
                ping = asyncio.ensure_future(socket.sleep(socket.ping_interval_s))
            else:
                return GOING_AWAY
    finally:
        await _cancel(next_event, ping, stopping)
