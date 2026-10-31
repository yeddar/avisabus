"""Clock port: the only way the application reads the current time."""

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Return the current instant as a timezone-aware UTC datetime."""
        ...
