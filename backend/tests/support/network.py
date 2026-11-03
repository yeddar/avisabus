"""In-memory `NetworkRepository` for the stop and arrivals use cases (never in production)."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from avisabus.domain.models.network import (
    FeedVersion,
    HeadsignAtStop,
    Line,
    LineDirection,
    ScheduledStopTime,
    Stop,
    TripStopTime,
)
from avisabus.domain.services.occupancy_simulation import service_day_start

FEED = FeedVersion(
    version_id=1,
    feed_version="test",
    imported_at=datetime(2026, 10, 31, tzinfo=UTC),
    start_date=date(2026, 10, 1),
    end_date=date(2026, 12, 31),
    counts={},
)


@dataclass
class FakeNetwork:
    """Only what `GetStop`, `GetStopArrivals` and `ScheduledArrivalsProvider` use.

    `scheduled` holds every passage; `scheduled_stop_times` filters them by stop and window like
    the SQLite repository (service day start + `arrival_s`), and records each query.
    """

    feed: FeedVersion | None = FEED
    stops: dict[str, Stop] = field(default_factory=dict)
    lines: dict[str, Line] = field(default_factory=dict)
    stop_lines: dict[str, list[LineDirection]] = field(default_factory=dict)
    headsigns: dict[tuple[str, str], list[HeadsignAtStop]] = field(default_factory=dict)
    departing: dict[tuple[str, str], frozenset[int]] = field(default_factory=dict)
    scheduled: dict[str, list[ScheduledStopTime]] = field(default_factory=lambda: defaultdict(list))
    trips: dict[str, list[TripStopTime]] = field(default_factory=dict)
    scheduled_queries: list[tuple[str, datetime, timedelta]] = field(default_factory=list)
    departing_queries: list[tuple[str, str]] = field(default_factory=list)

    def active_feed(self) -> FeedVersion | None:
        return self.feed

    def get_stop(self, stop_id: str) -> Stop | None:
        return self.stops.get(stop_id) if self.feed else None

    def get_line(self, short_name: str) -> Line | None:
        return self.lines.get(short_name) if self.feed else None

    def lines_at_stop(self, stop_id: str) -> list[LineDirection]:
        return list(self.stop_lines.get(stop_id, []))

    def headsigns_at_stop(self, stop_id: str, line: str) -> list[HeadsignAtStop]:
        return list(self.headsigns.get((stop_id, line), []))

    def departing_directions(self, stop_id: str, line: str) -> frozenset[int]:
        self.departing_queries.append((stop_id, line))
        return self.departing.get((stop_id, line), frozenset())

    def scheduled_stop_times(
        self, stop_id: str, at: datetime, window: timedelta
    ) -> list[ScheduledStopTime]:
        self.scheduled_queries.append((stop_id, at, window))
        found = [
            (passage_time(p), p)
            for p in self.scheduled.get(stop_id, [])
            if at <= passage_time(p) <= at + window
        ]
        found.sort(key=lambda item: (item[0], item[1].trip_id))
        return [p for _, p in found]

    def trip_stop_times(self, trip_id: str) -> list[TripStopTime]:
        return list(self.trips.get(trip_id, []))

    # Builders.

    def add_line(self, short_name: str, color: str = "FE0000", text_color: str = "FFFFFF") -> Line:
        line = Line(short_name, f"{short_name} - TEST", color, text_color, frozenset({short_name}))
        self.lines[short_name] = line
        return line

    def add_stop(self, stop_id: str, name: str, *directions: LineDirection) -> Stop:
        stop = Stop(stop_id, name, 39.47, -0.38)
        self.stops[stop_id] = stop
        self.stop_lines[stop_id] = list(directions)
        return stop

    def add_headsign(
        self, stop_id: str, line: str, direction_id: int, headsign: str, trips: int = 10
    ) -> None:
        self.headsigns.setdefault((stop_id, line), []).append(
            HeadsignAtStop(line, direction_id, headsign, trips)
        )

    def add_passage(
        self,
        stop_id: str,
        trip_id: str,
        line: str,
        direction_id: int,
        headsign: str,
        when: datetime,
        service_date: date,
    ) -> ScheduledStopTime:
        arrival_s = int((when - service_day_start(service_date)).total_seconds())
        passage = ScheduledStopTime(
            trip_id=trip_id,
            line=line,
            direction_id=direction_id,
            headsign=headsign,
            service_date=service_date,
            arrival_s=arrival_s,
            stop_sequence=5,
        )
        self.scheduled[stop_id].append(passage)
        self.trips.setdefault(
            trip_id,
            [
                TripStopTime("first", 1, arrival_s - 600, arrival_s - 600, None),
                TripStopTime(stop_id, 5, arrival_s, arrival_s, None),
                TripStopTime("last", 9, arrival_s + 600, arrival_s + 600, None),
            ],
        )
        return passage


def passage_time(passage: ScheduledStopTime) -> datetime:
    return service_day_start(passage.service_date) + timedelta(seconds=passage.arrival_s)


def line_direction(
    line: str, direction_id: int, headsign: str, color: str = "FE0000", text_color: str = "FFFFFF"
) -> LineDirection:
    return LineDirection(line, direction_id, headsign, color, text_color, f"shape_{line}")


class FakeStopTokenSigner:
    """Accepts only `token-of-<stop_id>` (padded to the real 22 characters)."""

    def sign(self, stop_id: str) -> str:
        return f"tok-{stop_id}".ljust(22, "_")[:22]

    def verify(self, stop_id: str, token: str) -> bool:
        return token == self.sign(stop_id)
