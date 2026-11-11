"""Read port of the transport network (gtfs_import design §3). Always the active feed version."""

from datetime import date, datetime, timedelta
from typing import Protocol

from avisabus.domain.models.network import (
    Departure,
    FeedVersion,
    HeadsignAtStop,
    Line,
    LineDirection,
    LineDirectionsView,
    ScheduledStopTime,
    ShapePoint,
    Stop,
    TripStopTime,
)
from avisabus.domain.models.position import ShapeStop


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
        """Passages in `[at, at + window]`, by time, of every service day from `date(at) - 1` to
        `date(at + window)` in the feed's zone (stop_arrivals_api AC-18)."""
        ...

    def departing_directions(self, stop_id: str, line: str) -> frozenset[int]:
        """Directions of `line` with some trip of the active feed whose first stop (minimum
        `stop_sequence`) is `stop_id`.

        Port extension defined by stop_arrivals_api design §3 ("Sentidos que salen", AC-19).
        """
        ...

    def trip_stop_times(self, trip_id: str) -> list[TripStopTime]: ...

    def trip_line(self, trip_id: str) -> str | None:
        """Commercial line (`route_short_name`) of the trip; `None` if it is not in the feed.

        Port extension defined by occupancy_sensor design §3 ("Forzado").
        """
        ...

    def shape_points(self, shape_id: str) -> list[ShapePoint]: ...

    def trip_shape_id(self, trip_id: str) -> str | None:
        """Shape of the trip; `None` if the trip is not in the active feed.

        Port extension defined by position_estimation design §3.
        """
        ...

    def shape_stops(self, shape_id: str) -> list[ShapeStop]:
        """Stops, in order, of the trip with the most frequent stop pattern among the trips with
        that shape (tie: the pattern of the smallest `trip_id`; its trip gives the sequences);
        `[]` if no trip uses the shape (position_estimation design §3)."""
        ...

    def shape_line(self, shape_id: str) -> Line | None:
        """Commercial line of the trips with that shape (the one with most trips, then the
        smallest name); `None` if no trip uses it (position_estimation design §3)."""
        ...

    def list_lines(self) -> list[LineDirectionsView]:
        """Lines of the active network in natural order, with their directions.

        Port extension defined by driver_session design §3.
        """
        ...

    def departures(
        self, line: str, direction_id: int, service_date: date, from_s: int, to_s: int
    ) -> list[Departure]:
        """Trips of `line` and `direction_id` with active service on `service_date` whose
        departure from the first stop (minimum `stop_sequence`) is in `[from_s, to_s]`, by time
        and then trip.

        Port extension defined by driver_session design §3.
        """
        ...
