"""Driver access codes (driver_codes_cli design §2, ADR-017) and shifts (driver_session design §3).

The plain code is never part of this model: only its keyed hash is kept. Codes are not tied to
people; the label is free text chosen by the administrator. A shift only keeps the SHA-256 of its
token and its last position, both left out of `repr` so that they cannot reach a log by accident.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

MAX_LABEL_LENGTH = 40


@dataclass(frozen=True, slots=True)
class DriverCode:
    code_id: str
    """`dc-` + 6 characters in [a-z0-9]."""
    code_hash: str = field(repr=False)
    """Hexadecimal keyed hash, left out of `repr` so that it cannot reach a log by accident."""
    label: str
    created_at: datetime
    revoked_at: datetime | None

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


def is_valid_driver_code_label(label: str) -> bool:
    """AC-02: from 1 to 40 printable characters; line breaks and controls are not printable."""
    return 1 <= len(label) <= MAX_LABEL_LENGTH and label.isprintable()


class SessionCloseReason(StrEnum):
    ENDED = "ENDED"
    IDLE = "IDLE"
    REVOKED = "REVOKED"
    REPLACED = "REPLACED"


class GpsState(StrEnum):
    WAITING = "WAITING"
    OK = "OK"
    STALE = "STALE"


@dataclass(frozen=True, slots=True)
class DriverService:
    """The departure (GTFS trip) a shift is driving (ADR-018)."""

    line: str
    direction_id: int
    trip_id: str
    service_date: date


@dataclass(frozen=True, slots=True)
class DriverPosition:
    lat: float
    lon: float
    accuracy_m: float
    recorded_at: datetime


@dataclass(frozen=True, slots=True)
class DriverSession:
    session_id: str
    """Random UUID v4."""
    token_hash: str = field(repr=False)
    """SHA-256 (hexadecimal) of the session token."""
    code_id: str
    started_at: datetime
    service: DriverService | None
    position: DriverPosition | None = field(repr=False)
    progress_m: float | None
    """Distance along the shape of the trip."""
    off_route: bool
    last_fix_at: datetime | None
    """Server instant of the last new GPS fix: a position with a later `recorded_at` (AC-11, v1.3).
    Resending the same position does not renew it, so a lost GPS turns `STALE`."""
    last_seen_at: datetime | None
    """Server instant of the last valid `PUT …/position`, even a resend (AC-13, v1.3): the sign of
    life that keeps the shift open."""
    progress_recorded_at: datetime | None = None
    """`recorded_at` of the last position accepted on the route (AC-09, v1.1)."""


@dataclass(frozen=True, slots=True)
class UpcomingStop:
    stop_id: str
    name: str
    stop_sequence: int
    distance_m: float
    """Along the shape, from the current progress."""


@dataclass(frozen=True, slots=True)
class SessionProgress:
    gps: GpsState
    off_route: bool
    finished: bool
    upcoming: tuple[UpcomingStop, ...]
    """Up to 5."""
