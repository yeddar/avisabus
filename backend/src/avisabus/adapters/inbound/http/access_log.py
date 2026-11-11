"""Keeps the client address out of the logs of the driver endpoints (driver_session AC-15).

uvicorn's access log is a standard record whose arguments are the client address, the method, the
path, the HTTP version and the status. On `/driver` the address is masked; the rest of the line
carries neither the token (a header) nor the coordinates (a body).

The WebSocket connections are not in that log: uvicorn writes them in its server log as
`<address> - "WebSocket <path>" [accepted]` (or a status). On `/ws/driver` the address is masked
and the query string dropped, since a client could send anything there (driver_demand AC-12).
"""

import logging

ACCESS_LOGGER = "uvicorn.access"
SERVER_LOGGER = "uvicorn.error"
MASKED_ADDRESS = "-"
_CLIENT, _PATH = 0, 2
_WEBSOCKET_FORMAT = '%s - "WebSocket %s"'
_SOCKET_PATH = 1


class DriverAddressFilter(logging.Filter):
    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) > _PATH and self._is_driver(str(args[_PATH])):
            record.args = (MASKED_ADDRESS, *args[_CLIENT + 1 :])
        return True

    def _is_driver(self, path: str) -> bool:
        return path == self._path or path.startswith((f"{self._path}/", f"{self._path}?"))


def mask_driver_addresses(path: str) -> None:
    """Idempotent: the filter is installed at most once, whatever the number of applications."""
    logger = logging.getLogger(ACCESS_LOGGER)
    if not any(isinstance(existing, DriverAddressFilter) for existing in logger.filters):
        logger.addFilter(DriverAddressFilter(path))


class DriverSocketAddressFilter(logging.Filter):
    def __init__(self, path: str) -> None:
        super().__init__()
        self._path = path

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if (
            isinstance(record.msg, str)
            and record.msg.startswith(_WEBSOCKET_FORMAT)
            and isinstance(args, tuple)
            and len(args) > _SOCKET_PATH
            and self._is_driver(str(args[_SOCKET_PATH]))
        ):
            record.args = (MASKED_ADDRESS, self._path, *args[_SOCKET_PATH + 1 :])
        return True

    def _is_driver(self, path: str) -> bool:
        return path == self._path or path.startswith(f"{self._path}?")


def mask_driver_socket_addresses(path: str) -> None:
    """Idempotent, like `mask_driver_addresses`."""
    logger = logging.getLogger(SERVER_LOGGER)
    if not any(isinstance(existing, DriverSocketAddressFilter) for existing in logger.filters):
        logger.addFilter(DriverSocketAddressFilter(path))
