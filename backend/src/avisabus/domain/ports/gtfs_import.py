"""Ports used to import a GTFS feed (gtfs_import design §2 and §5)."""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Literal, Protocol, Self

from avisabus.domain.models.network import CalendarException, FeedVersion, ServiceCalendar

DirectionSource = Literal["feed", "derived"]


@dataclass(frozen=True, slots=True)
class GtfsRow:
    """Raw CSV row: column name -> text exactly as in the file (missing cells are `""`)."""

    line_number: int
    values: Mapping[str, str]


class GtfsFeedReader(Protocol):
    """Streaming access to the files of a feed (directory or zip)."""

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    def validate(self) -> None:
        """Check required files and columns; raise `GtfsValidationError` otherwise."""
        ...

    def has_file(self, name: str) -> bool: ...

    def columns(self, name: str) -> Sequence[str]: ...

    def iter_rows(self, name: str) -> Iterator[GtfsRow]:
        """Yield the rows of `name` one by one; raise `GtfsDataError` on undecodable data."""
        ...


# Typed records handed to the writer (names already cleaned, times in seconds).


@dataclass(frozen=True, slots=True)
class RouteRecord:
    route_id: str
    short_name: str
    long_name: str
    color: str
    text_color: str


@dataclass(frozen=True, slots=True)
class StopRecord:
    stop_id: str
    name: str
    lat: float
    lon: float


@dataclass(frozen=True, slots=True)
class ShapePointRecord:
    shape_id: str
    sequence: int
    lat: float
    lon: float
    dist: float | None


@dataclass(frozen=True, slots=True)
class TripRecord:
    trip_id: str
    route_id: str
    service_id: str
    headsign: str | None
    """`None` when the feed has no `trip_headsign` (the last stop name is used)."""
    shape_id: str
    direction_id: int | None
    """`None` when `trips.txt` has no `direction_id` (derived on import)."""


@dataclass(frozen=True, slots=True)
class StopTimeRecord:
    trip_id: str
    stop_sequence: int
    stop_id: str
    arrival_s: int
    departure_s: int
    shape_dist: float | None


GtfsRecord = (
    RouteRecord
    | StopRecord
    | ServiceCalendar
    | CalendarException
    | ShapePointRecord
    | TripRecord
    | StopTimeRecord
)


@dataclass(frozen=True, slots=True)
class DerivedSummary:
    lines: int
    ignored_route_ids: int


class GtfsFeedWriter(Protocol):
    """Versioned storage of a feed. Nothing is visible to readers until `activate`."""

    def begin_version(self) -> int:
        """Create an inactive version and return its id."""
        ...

    def insert_batch(self, version_id: int, records: Sequence[GtfsRecord]) -> None:
        """Insert a batch of records, all of the same type."""
        ...

    def build_derived(self, version_id: int, directions_from_feed: bool) -> DerivedSummary:
        """Fill headsigns, directions (derived unless `directions_from_feed`) and derived
        tables (design §5)."""
        ...

    def activate(self, feed: FeedVersion, timezone: str) -> None:
        """Store the metadata of `feed` and make it the only active version (one transaction)."""
        ...

    def purge_inactive(self) -> None:
        """Delete the data of every version that is not active."""
        ...

    def discard(self, version_id: int) -> None:
        """Delete every row of a (failed) version."""
        ...


@dataclass(frozen=True, slots=True)
class StopRef:
    stop_id: str
    name: str


@dataclass(frozen=True, slots=True)
class DirectionReport:
    """Diagnostics of one line direction (`avisabus gtfs info --directions`, AC-26)."""

    line: str
    direction_id: int
    source: DirectionSource
    trip_count: int
    main_shape_id: str
    first_stop: StopRef
    last_stop: StopRef
    headsigns: tuple[tuple[str, int], ...]
    """(headsign, trip_count), most frequent first."""
    patterns: tuple[tuple[str, int], ...]
    """(shape_id, trip_count), most frequent first."""


class DirectionReportSource(Protocol):
    def direction_report(self) -> list[DirectionReport]:
        """Every (line, direction) of the active feed, lines in natural order."""
        ...
