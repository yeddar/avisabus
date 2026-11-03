"""Estimated position of a bus and the shape of a trip (position_estimation design §3).

EMT València does not publish where its buses are (ADR-005, LIM-03): the position is estimated
from the arrival time, the paired trip and its timetable and shape.
"""

from dataclasses import dataclass
from enum import StrEnum


class PositionStatus(StrEnum):
    EN_ROUTE = "EN_ROUTE"
    """Between two stops before the target one."""
    AT_STOP = "AT_STOP"
    """At the target stop (its scheduled time, shifted by the delay, has come)."""
    NOT_STARTED = "NOT_STARTED"
    """At the first stop of the trip, before its departure."""
    NO_VEHICLE = "NO_VEHICLE"
    """There is an arrival, but it is not paired with any trip."""
    NO_ARRIVAL = "NO_ARRIVAL"
    """No arrival of the line and direction."""


@dataclass(frozen=True, slots=True)
class StopRef:
    stop_id: str
    name: str


@dataclass(frozen=True, slots=True)
class PositionEstimate:
    status: PositionStatus
    """EN_ROUTE, AT_STOP or NOT_STARTED."""
    lat: float
    lon: float
    bearing_deg: float | None
    shape_distance_m: float
    """Distance along the shape of the trip."""
    distance_to_stop_m: float
    """Along the shape, up to the target stop; never negative."""
    stops_away: int
    """Stops before the target one still ahead of the bus (0: the next one is yours)."""
    next_stop: StopRef


@dataclass(frozen=True, slots=True)
class ShapeStop:
    stop_id: str
    name: str
    lat: float
    lon: float
    sequence: int


@dataclass(frozen=True, slots=True)
class ShapeView:
    shape_id: str
    line: str
    color: str | None
    coordinates: tuple[tuple[float, float], ...]
    """(lon, lat), in the order of the shape."""
    stops: tuple[ShapeStop, ...]
    feed_version_id: int
