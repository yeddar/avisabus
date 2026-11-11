"""Ports of the driver access codes (driver_codes_cli design §2) and shifts (driver_session
design §3)."""

from datetime import date, datetime
from typing import Protocol

from avisabus.domain.models.driver import (
    DriverCode,
    DriverService,
    DriverSession,
    SessionCloseReason,
)


class DriverCodeHasher(Protocol):
    def hash(self, code: str) -> str:
        """Keyed hash (hexadecimal) of a code of 8 digits without spaces."""
        ...


class CodeGenerator(Protocol):
    def new_code(self) -> str:
        """A new code of 8 digits, with leading zeros."""
        ...

    def new_code_id(self) -> str:
        """A new identifier: `dc-` + 6 characters in [a-z0-9]."""
        ...


class DriverCodeRepository(Protocol):
    def add(self, code: DriverCode) -> None:
        """Store the code. Raises `DriverCodeCollisionError` if its hash or id already exist."""
        ...

    def get(self, code_id: str) -> DriverCode | None: ...

    def find_by_hash(self, code_hash: str) -> DriverCode | None: ...

    def list_all(self) -> list[DriverCode]:
        """Every code, active or revoked, ordered by `created_at`."""
        ...

    def revoke(self, code_id: str, at: datetime) -> DriverCode | None:
        """Mark the code as revoked at `at` and return it; `None` if it does not exist. A code
        that was already revoked keeps its original date."""
        ...


class SessionTokenHasher(Protocol):
    def hash(self, token: str) -> str:
        """SHA-256 (hexadecimal) of a session token."""
        ...


class DriverSessionRepository(Protocol):
    def add(self, session: DriverSession) -> None: ...

    def by_token_hash(self, token_hash: str) -> DriverSession | None: ...

    def by_code(self, code_id: str) -> DriverSession | None: ...

    def by_trip(self, trip_id: str, service_date: date) -> DriverSession | None: ...

    def list_all(self) -> list[DriverSession]: ...

    def save(self, session: DriverSession) -> None:
        """Store the changes. Raises `DepartureTakenError` if another shift holds its departure."""
        ...

    def delete(self, session_id: str) -> bool:
        """Delete the session with its position; `False` if it no longer exists."""
        ...


class DriverSessionListener(Protocol):
    """Implemented by `driver_demand`."""

    def service_selected(self, session: DriverSession, previous: DriverService | None) -> None: ...

    def position_updated(self, session: DriverSession) -> None: ...

    def session_closed(self, session_id: str, reason: SessionCloseReason) -> None: ...
