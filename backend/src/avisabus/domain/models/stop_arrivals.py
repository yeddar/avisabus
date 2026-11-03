"""Read models of the stop view and its arrivals (stop_arrivals_api design §3)."""

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from avisabus.domain.models.arrivals import ArrivalKind
from avisabus.domain.models.network import LineDirection
from avisabus.domain.models.occupancy import OccupancyStatus


class ArrivalSource(StrEnum):
    REALTIME = "REALTIME"
    """Arrivals of the SAE."""
    SCHEDULED = "SCHEDULED"
    """Fallback to the GTFS timetable when the SAE is unavailable (RF-09)."""


@dataclass(frozen=True, slots=True)
class VehicleView:
    """Identity of the bus: the GTFS trip paired with the arrival and its service day."""

    trip_id: str
    service_date: date


@dataclass(frozen=True, slots=True)
class ArrivalView:
    line: str
    destination: str
    """GTFS headsign when the direction is resolved, otherwise the SAE text (AC-09)."""
    direction_id: int | None
    in_network: bool
    kind: ArrivalKind
    minutes: int | None
    arrival_at: datetime
    """Timezone-aware UTC."""
    line_color: str | None
    line_text_color: str | None
    sae_destination: str | None
    """SAE text as given; `None` when the source is SCHEDULED (AC-21)."""
    vehicle: VehicleView | None
    occupancy: OccupancyStatus | None
    can_alert: bool


@dataclass(frozen=True, slots=True)
class StopView:
    stop_id: str
    name: str
    lines: tuple[LineDirection, ...]


@dataclass(frozen=True, slots=True)
class StopArrivals:
    stop_id: str
    source: ArrivalSource
    generated_at: datetime
    """Timezone-aware UTC, read from the `Clock`."""
    refresh_after_s: int
    arrivals: tuple[ArrivalView, ...]
    """Sorted by `arrival_at`."""
