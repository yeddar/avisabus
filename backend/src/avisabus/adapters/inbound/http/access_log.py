"""Keeps the client address out of the access log of the driver endpoints (driver_session AC-15).

uvicorn's access log is a standard record whose arguments are the client address, the method, the
path, the HTTP version and the status. On `/driver` the address is masked; the rest of the line
carries neither the token (a header) nor the coordinates (a body).
"""

import logging

ACCESS_LOGGER = "uvicorn.access"
MASKED_ADDRESS = "-"
_CLIENT, _PATH = 0, 2


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
