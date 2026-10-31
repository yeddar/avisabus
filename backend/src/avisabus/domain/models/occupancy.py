"""Vehicle occupancy models (occupancy_sensor design §3).

EMT does not identify vehicles, so the bus is identified by the GTFS trip paired with its ETA
and the service day it belongs to (ADR-013).
"""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class VehicleRef:
    trip_id: str
    service_date: date


@dataclass(frozen=True, slots=True)
class OccupancyReading:
    capacity: int
    seats: int
    occupied: int
    measured_at: datetime

    @property
    def free_places(self) -> int:
        return self.capacity - self.occupied

    @property
    def free_seats(self) -> int:
        return max(0, self.seats - self.occupied)


class OccupancyLevel(StrEnum):
    FREE = "FREE"
    MEDIUM = "MEDIUM"
    FULL = "FULL"


@dataclass(frozen=True, slots=True)
class OccupancyThresholds:
    """`occupied / capacity` below `medium` is FREE, below `full` is MEDIUM, otherwise FULL."""

    medium: float = 0.50
    full: float = 0.85


@dataclass(frozen=True, slots=True)
class OccupancyStatus:
    level: OccupancyLevel
    has_free_seats: bool
    free_seats: int
    free_places: int
    ratio: float
