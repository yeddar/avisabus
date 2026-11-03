"""Normalised real-time arrivals (sae_arrivals_source design §3).

The raw format of the SAE is isolated in the outbound parser: the rest of the system only sees
these models.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ArrivalKind(StrEnum):
    MINUTES = "MINUTES"
    CLOCK_TIME = "CLOCK_TIME"


@dataclass(frozen=True, slots=True)
class SaeArrival:
    line: str
    """As given by the SAE (e.g. "93", "C2", "N4")."""
    destination: str
    """As given by the SAE (e.g. "Pass. Marítim")."""
    kind: ArrivalKind
    minutes: int | None
    """Only when `kind` is MINUTES."""
    arrival_at: datetime
    """Timezone-aware UTC."""


@dataclass(frozen=True, slots=True)
class ArrivalsSnapshot:
    stop_id: str
    fetched_at: datetime
    """Timezone-aware UTC, read from the `Clock`."""
    arrivals: tuple[SaeArrival, ...]
    """In the order given by the SAE."""
