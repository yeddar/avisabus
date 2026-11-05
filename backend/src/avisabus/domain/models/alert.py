"""Stop request ("aviso", `Alert`) of a passenger to a chosen bus (alert_create design §3).

In the interface it is a "solicitud de parada"; the bus is the GTFS trip paired with the arrival
the passenger chose (ADR-013, ADR-016).
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


class Need(StrEnum):
    """Accessibility need of the passenger (RF-17 v1.1). Only stored inside its alert (RNF-06)."""

    RAMP = "RAMP"
    EXTRA_TIME = "EXTRA_TIME"
    SEAT = "SEAT"
    VISUAL = "VISUAL"


NEED_ORDER: tuple[Need, ...] = (Need.RAMP, Need.EXTRA_TIME, Need.SEAT, Need.VISUAL)
"""Canonical order of the needs in an alert and in its answers (AC-06)."""


def canonical_needs(needs: Iterable[Need]) -> tuple[Need, ...]:
    """The needs in canonical order. Raises `ValueError` if one is repeated (AC-06)."""
    given = list(needs)
    if len(set(given)) != len(given):
        raise ValueError("repeated needs")
    return tuple(need for need in NEED_ORDER if need in given)


class AlertStatus(StrEnum):
    PENDING_DRIVER = "PENDING_DRIVER"
    """Registered, no driver connected to that bus (always in block 3)."""
    DELIVERED = "DELIVERED"
    """Delivered to the driver session of that bus."""
    # EXPIRED / CANCELLED only exist in the final events: the alert is deleted (RNF-06).


@dataclass(frozen=True, slots=True)
class AlertTracking:
    """Tracking of the trip at the stop (used by `alert_expiry`)."""

    last_seen_at: datetime | None
    """Last REALTIME observation in which the trip appeared; `None` until there is one."""
    last_arrival_at: datetime
    """Its `arrival_at` then (on creation: the one of the chosen arrival)."""
    last_delay_s: int
    """`arrival_at` − scheduled time at the stop, in seconds (on creation: the chosen one's)."""


@dataclass(frozen=True, slots=True)
class Alert:
    alert_id: str
    """Random UUID v4."""
    device_hash: str
    stop_id: str
    stop_name: str
    line: str
    direction_id: int
    destination: str
    """`ArrivalView.destination` of the chosen arrival."""
    trip_id: str
    service_date: date
    stop_sequence: int
    """Occurrence of the stop in the trip (circular lines: the one closest to `arrival_at`)."""
    needs: tuple[Need, ...]
    """Canonical order, no repeats."""
    status: AlertStatus
    delivered_to: str | None
    """Session of the driver (block 4)."""
    created_at: datetime
    expires_at: datetime
    """`created_at` + max age (RF-21)."""
    tracking: AlertTracking
