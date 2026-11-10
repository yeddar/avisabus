"""What the driver sees (driver_demand design §3): next stops, demand, free places and alerts.

Privacy (AC-05): the view holds aggregated needs per stop and the `alert_id` of each request,
never anything about the device of the passenger.
"""

from dataclasses import dataclass
from datetime import date, datetime

from avisabus.domain.models.driver import GpsState


@dataclass(frozen=True, slots=True)
class NeedCounts:
    """How many requests of a stop have each need."""

    RAMP: int = 0
    EXTRA_TIME: int = 0
    SEAT: int = 0
    VISUAL: int = 0


@dataclass(frozen=True, slots=True)
class StopDemand:
    stop_id: str
    name: str
    stop_sequence: int
    distance_m: float
    """Along the shape, from the bus."""
    waiting: int
    """Requests delivered to this shift in this occurrence of the stop."""
    needs: NeedCounts
    alert_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DriverServiceView:
    line: str
    direction_id: int
    headsign: str
    trip_id: str
    service_date: date
    departure_at: datetime
    color: str
    text_color: str


@dataclass(frozen=True, slots=True)
class DriverView:
    generated_at: datetime
    service: DriverServiceView | None
    """`None` without a chosen departure (AC-07)."""
    gps: GpsState
    off_route: bool
    finished: bool
    stops: tuple[StopDemand, ...]
    """Up to 5."""
    total_waiting: int
    free_places: int | None
    """`None` without occupancy data."""
    free_seats: int | None
    capacity_alert: bool
    seat_alert: bool
