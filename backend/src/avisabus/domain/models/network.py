"""Transport network read models (GTFS-derived). Names are kept as they come in the feed."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class Stop:
    stop_id: str
    name: str
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class Line:
    """Commercial line: every `route_id` sharing a `route_short_name`."""

    short_name: str
    long_name: str
    color: str
    text_color: str
    route_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class LineDirection:
    line: str
    direction_id: int
    headsign: str
    color: str
    text_color: str
    shape_id: str


@dataclass(frozen=True, slots=True)
class ShapePoint:
    lat: float
    lon: float
    sequence: int
    dist_traveled: float | None


@dataclass(frozen=True, slots=True)
class ScheduledStopTime:
    trip_id: str
    line: str
    direction_id: int
    headsign: str
    service_date: date
    """Service day the trip belongs to."""
    arrival_s: int
    """Seconds since the start of `service_date` (may be >= 86400)."""
    stop_sequence: int


@dataclass(frozen=True, slots=True)
class TripStopTime:
    stop_id: str
    stop_sequence: int
    arrival_s: int
    departure_s: int
    shape_dist_traveled: float | None


@dataclass(frozen=True, slots=True)
class HeadsignAtStop:
    line: str
    direction_id: int
    headsign: str
    trip_count: int


@dataclass(frozen=True, slots=True)
class FeedVersion:
    version_id: int
    feed_version: str | None
    imported_at: datetime
    start_date: date
    end_date: date
    counts: Mapping[str, int]
