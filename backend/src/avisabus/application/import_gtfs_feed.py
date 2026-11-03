"""Use case: import a GTFS feed into a new version and activate it (gtfs_import design §5)."""

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from zoneinfo import ZoneInfo

from avisabus.application import gtfs_rows
from avisabus.application.errors import GtfsDataError
from avisabus.domain.models.network import CalendarException, FeedVersion, ServiceCalendar
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.gtfs_import import (
    GtfsFeedReader,
    GtfsFeedWriter,
    GtfsRecord,
    GtfsRow,
    TripRecord,
)
from avisabus.domain.services.feed_validity import (
    DEFAULT_WARNING_DAYS,
    FeedValidityStatus,
    MissingValidityRangeError,
    feed_validity_range,
    feed_validity_status,
)

DEFAULT_BATCH_SIZE = 10_000


@dataclass(frozen=True, slots=True)
class ImportGtfsFeedCommand:
    path: Path
    """Directory or `.zip` with the GTFS files at its root."""


@dataclass(frozen=True, slots=True)
class ImportGtfsFeedResult:
    feed: FeedVersion
    validity: FeedValidityStatus
    ignored_route_ids: int


@dataclass(slots=True)
class _Progress:
    route_ids: set[str]
    calendars: list[ServiceCalendar]
    exceptions: list[CalendarException]
    counts: dict[str, int]


class ImportGtfsFeed:
    def __init__(
        self,
        open_reader: Callable[[Path], GtfsFeedReader],
        writer: GtfsFeedWriter,
        clock: Clock,
        batch_size: int = DEFAULT_BATCH_SIZE,
        warning_days: int = DEFAULT_WARNING_DAYS,
    ) -> None:
        self._open_reader = open_reader
        self._writer = writer
        self._clock = clock
        self._batch_size = batch_size
        self._warning_days = warning_days

    async def execute(self, command: ImportGtfsFeedCommand) -> ImportGtfsFeedResult:
        with self._open_reader(command.path) as reader:
            reader.validate()
            version_id = self._writer.begin_version()
            try:
                feed, timezone, ignored = self._load(reader, version_id)
                self._writer.activate(feed, timezone)
            except BaseException:
                self._writer.discard(version_id)
                raise
        self._writer.purge_inactive()
        today = self._clock.now().astimezone(ZoneInfo(timezone)).date()
        validity = feed_validity_status(feed, today, self._warning_days)
        return ImportGtfsFeedResult(feed=feed, validity=validity, ignored_route_ids=ignored)

    def _load(self, reader: GtfsFeedReader, version_id: int) -> tuple[FeedVersion, str, int]:
        timezone = self._timezone(reader)
        feed_version, feed_start, feed_end = self._feed_info(reader)
        has_direction = "direction_id" in reader.columns("trips.txt")
        progress = _Progress(set(), [], [], {"stops": 0, "trips": 0, "stop_times": 0})

        def route(row: GtfsRow) -> GtfsRecord:
            record = gtfs_rows.route_record(row)
            progress.route_ids.add(record.route_id)
            return record

        def calendar(row: GtfsRow) -> GtfsRecord:
            record = gtfs_rows.calendar_record(row)
            progress.calendars.append(record)
            return record

        def calendar_date(row: GtfsRow) -> GtfsRecord:
            record = gtfs_rows.calendar_date_record(row)
            progress.exceptions.append(record)
            return record

        def trip(row: GtfsRow) -> GtfsRecord:
            record: TripRecord = gtfs_rows.trip_record(row, has_direction)
            if record.route_id not in progress.route_ids:
                raise GtfsDataError("trips.txt", row.line_number, "unknown route_id")
            return record

        steps: list[tuple[str, Callable[[GtfsRow], GtfsRecord], str | None]] = [
            ("routes.txt", route, None),
            ("stops.txt", gtfs_rows.stop_record, "stops"),
            ("calendar.txt", calendar, None),
            ("calendar_dates.txt", calendar_date, None),
            ("shapes.txt", gtfs_rows.shape_point_record, None),
            ("trips.txt", trip, "trips"),
            ("stop_times.txt", gtfs_rows.stop_time_record, "stop_times"),
        ]
        for name, convert, counter in steps:
            if not reader.has_file(name):
                continue
            inserted = self._copy(reader.iter_rows(name), convert, version_id)
            if counter is not None:
                progress.counts[counter] = inserted

        derived = self._writer.build_derived(version_id, directions_from_feed=has_direction)
        start, end = self._validity_range(feed_start, feed_end, progress)
        counts = {
            "lines": derived.lines,
            **progress.counts,
            "ignored_route_ids": derived.ignored_route_ids,
        }
        feed = FeedVersion(
            version_id=version_id,
            feed_version=feed_version,
            imported_at=self._clock.now(),
            start_date=start,
            end_date=end,
            counts=counts,
        )
        return feed, timezone, derived.ignored_route_ids

    def _copy(
        self, rows: Iterator[GtfsRow], convert: Callable[[GtfsRow], GtfsRecord], version_id: int
    ) -> int:
        total = 0
        batch: list[GtfsRecord] = []
        for row in rows:
            batch.append(convert(row))
            if len(batch) >= self._batch_size:
                self._writer.insert_batch(version_id, batch)
                total += len(batch)
                batch = []
        if batch:
            self._writer.insert_batch(version_id, batch)
            total += len(batch)
        return total

    @staticmethod
    def _timezone(reader: GtfsFeedReader) -> str:
        for row in reader.iter_rows("agency.txt"):
            return gtfs_rows.agency_timezone(row)
        raise GtfsDataError("agency.txt", 2, "no agency")

    @staticmethod
    def _feed_info(reader: GtfsFeedReader) -> tuple[str | None, date | None, date | None]:
        if reader.has_file("feed_info.txt"):
            for row in reader.iter_rows("feed_info.txt"):
                return gtfs_rows.feed_info(row)
        return None, None, None

    @staticmethod
    def _validity_range(
        feed_start: date | None, feed_end: date | None, progress: _Progress
    ) -> tuple[date, date]:
        try:
            return feed_validity_range(
                feed_start, feed_end, progress.calendars, progress.exceptions
            )
        except MissingValidityRangeError as error:
            raise GtfsDataError("calendar.txt", 0, "no validity dates in the feed") from error
