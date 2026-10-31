"""Read port of the transport network (gtfs_import design §3). Always the active feed version."""

from datetime import date, datetime, timedelta
from typing import Protocol

from avisabus.domain.models.network import (
    FeedVersion,
    HeadsignAtStop,
    Line,
    LineDirection,
    ScheduledStopTime,
    ShapePoint,
    Stop,
    TripStopTime,
)


class NetworkRepository(Protocol):
    def active_feed(self) -> FeedVersion | None: ...

    def get_stop(self, stop_id: str) -> Stop | None: ...

    def list_stop_ids(self) -> list[str]: ...

    def get_line(self, short_name: str) -> Line | None: ...

    def lines_at_stop(self, stop_id: str) -> list[LineDirection]:
        """(line, direction) pairs serving the stop, lines in natural order."""
        ...

    def headsigns_at_stop(self, stop_id: str, line: str) -> list[HeadsignAtStop]: ...

    def line_directions(self, line: str) -> list[LineDirection]: ...

    def shapes_for_direction(self, line: str, direction_id: int) -> list[tuple[str, int]]:
        """(shape_id, trip_count) sorted by trip_count desc, then shape_id asc."""
        ...

    def line_direction(self, line: str, direction_id: int) -> LineDirection | None: ...

    def active_service_ids(self, service_date: date) -> frozenset[str]: ...

    def scheduled_stop_times(
        self, stop_id: str, at: datetime, window: timedelta
    ) -> list[ScheduledStopTime]:
        """Passages in `[at, at + window]` of the service days `D` and `D - 1`, by time."""
        ...

    def trip_stop_times(self, trip_id: str) -> list[TripStopTime]: ...

    def shape_points(self, shape_id: str) -> list[ShapePoint]: ...
