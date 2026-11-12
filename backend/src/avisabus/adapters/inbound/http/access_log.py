"""Keeps the client address and the query string out of uvicorn's access logs (deployment_rpi
AC-09, which generalises driver_session AC-15 and driver_demand AC-12 to every path).

uvicorn's access log (`uvicorn.access`) is a standard record whose arguments are the client
address, the method, the path with its query string, the HTTP version and the status. The
address becomes `-` and the query string is dropped: the QR token (`?t=`) of `/api/v1/stops/…`
and `/p/…`, or anything a client sends, never reaches the log.

The WebSocket connections are not in that log: uvicorn writes them in its server log
(`uvicorn.error`) as `<address> - "WebSocket <path>" [accepted]` (or a status). They get the same
treatment. Other server lines are left as they are.
"""

import logging

ACCESS_LOGGER = "uvicorn.access"
SERVER_LOGGER = "uvicorn.error"
MASKED_ADDRESS = "-"
_ACCESS_CLIENT, _ACCESS_PATH = 0, 2
_WEBSOCKET_FORMAT = '%s - "WebSocket %s"'
_SOCKET_CLIENT, _SOCKET_PATH = 0, 1


def _without_query(path: object) -> str:
    return str(path).split("?", 1)[0]


class ClientAddressFilter(logging.Filter):
    """`uvicorn.access`: no client address and no query string, on every path."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) > _ACCESS_PATH:
            record.args = (
                MASKED_ADDRESS,
                *args[_ACCESS_CLIENT + 1 : _ACCESS_PATH],
                _without_query(args[_ACCESS_PATH]),
                *args[_ACCESS_PATH + 1 :],
            )
        return True


class SocketAddressFilter(logging.Filter):
    """`uvicorn.error`: the WebSocket lines lose the client address and the query string."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if (
            isinstance(record.msg, str)
            and record.msg.startswith(_WEBSOCKET_FORMAT)
            and isinstance(args, tuple)
            and len(args) > _SOCKET_PATH
        ):
            record.args = (
                MASKED_ADDRESS,
                _without_query(args[_SOCKET_PATH]),
                *args[_SOCKET_PATH + 1 :],
            )
        return True


def mask_client_addresses() -> None:
    """Idempotent: each filter is installed at most once, whatever the number of applications."""
    for name, kind in ((ACCESS_LOGGER, ClientAddressFilter), (SERVER_LOGGER, SocketAddressFilter)):
        logger = logging.getLogger(name)
        if not any(isinstance(existing, kind) for existing in logger.filters):
            logger.addFilter(kind())
