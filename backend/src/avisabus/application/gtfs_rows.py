"""Conversion of raw GTFS rows into typed records (gtfs_import design §4.1).

Names and headsigns are only trimmed (AC-07); times become seconds since the start of the
service day (AC-08). Invalid values raise `GtfsDataError` with the file and line number.
"""

from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from avisabus.application.errors import GtfsDataError
from avisabus.domain.models.network import CalendarException, ServiceCalendar
from avisabus.domain.ports.gtfs_import import (
    GtfsRow,
    RouteRecord,
    ShapePointRecord,
    StopRecord,
    StopTimeRecord,
    TripRecord,
)
from avisabus.domain.services.gtfs_text import clean_name
from avisabus.domain.services.gtfs_time import InvalidGtfsTimeError, parse_gtfs_time

DEFAULT_COLOR = "FE0000"
DEFAULT_TEXT_COLOR = "FFFFFF"
WEEKDAY_COLUMNS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
EXCEPTION_TYPES = (1, 2)
DIRECTION_IDS = ("0", "1")


class _Fields:
    """Typed access to the values of one row; errors point to the file and line."""

    def __init__(self, file: str, row: GtfsRow) -> None:
        self.file = file
        self.row = row

    def error(self, detail: str) -> GtfsDataError:
        return GtfsDataError(self.file, self.row.line_number, detail)

    def raw(self, column: str) -> str:
        return self.row.values.get(column, "")

    def required(self, column: str) -> str:
        value = self.raw(column)
        if not value.strip():
            raise self.error(f"empty {column}")
        return value

    def name(self, column: str) -> str:
        return clean_name(self.raw(column))

    def integer(self, column: str) -> int:
        return self._convert(column, int)

    def real(self, column: str) -> float:
        return self._convert(column, float)

    def optional_real(self, column: str) -> float | None:
        return None if not self.raw(column).strip() else self.real(column)

    def day(self, column: str) -> date:
        return self._convert(column, _parse_date)

    def optional_day(self, column: str) -> date | None:
        return None if not self.raw(column).strip() else self.day(column)

    def time(self, column: str) -> int:
        try:
            return parse_gtfs_time(self.raw(column))
        except InvalidGtfsTimeError as error:
            raise self.error(f"invalid {column}") from error

    def _convert[T](self, column: str, convert: Callable[[str], T]) -> T:
        try:
            return convert(self.raw(column).strip())
        except ValueError as error:
            raise self.error(f"invalid {column}") from error


def _parse_date(value: str) -> date:
    if len(value) != 8 or not value.isdigit():
        raise ValueError(value)
    return datetime.strptime(value, "%Y%m%d").date()  # noqa: DTZ007 - calendar date only


def agency_timezone(row: GtfsRow) -> str:
    fields = _Fields("agency.txt", row)
    timezone = fields.required("agency_timezone").strip()
    try:
        ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise fields.error("invalid agency_timezone") from error
    return timezone


def feed_info(row: GtfsRow) -> tuple[str | None, date | None, date | None]:
    """(feed_version, feed_start_date, feed_end_date); empty values are `None`."""
    fields = _Fields("feed_info.txt", row)
    version = fields.name("feed_version") or None
    return version, fields.optional_day("feed_start_date"), fields.optional_day("feed_end_date")


def route_record(row: GtfsRow) -> RouteRecord:
    fields = _Fields("routes.txt", row)
    return RouteRecord(
        route_id=fields.required("route_id"),
        short_name=clean_name(fields.required("route_short_name")),
        long_name=fields.name("route_long_name"),
        color=fields.raw("route_color").strip() or DEFAULT_COLOR,
        text_color=fields.raw("route_text_color").strip() or DEFAULT_TEXT_COLOR,
    )


def stop_record(row: GtfsRow) -> StopRecord:
    fields = _Fields("stops.txt", row)
    return StopRecord(
        stop_id=fields.required("stop_id"),
        name=fields.name("stop_name"),
        lat=fields.real("stop_lat"),
        lon=fields.real("stop_lon"),
    )


def calendar_record(row: GtfsRow) -> ServiceCalendar:
    fields = _Fields("calendar.txt", row)
    weekdays = []
    for column in WEEKDAY_COLUMNS:
        value = fields.raw(column).strip()
        if value not in ("0", "1"):
            raise fields.error(f"invalid {column}")
        weekdays.append(value == "1")
    return ServiceCalendar(
        service_id=fields.required("service_id"),
        weekdays=(
            weekdays[0],
            weekdays[1],
            weekdays[2],
            weekdays[3],
            weekdays[4],
            weekdays[5],
            weekdays[6],
        ),
        start_date=fields.day("start_date"),
        end_date=fields.day("end_date"),
    )


def calendar_date_record(row: GtfsRow) -> CalendarException:
    fields = _Fields("calendar_dates.txt", row)
    exception_type = fields.integer("exception_type")
    if exception_type not in EXCEPTION_TYPES:
        raise fields.error("invalid exception_type")
    return CalendarException(
        service_id=fields.required("service_id"),
        date=fields.day("date"),
        exception_type=exception_type,
    )


def shape_point_record(row: GtfsRow) -> ShapePointRecord:
    fields = _Fields("shapes.txt", row)
    return ShapePointRecord(
        shape_id=fields.required("shape_id"),
        sequence=fields.integer("shape_pt_sequence"),
        lat=fields.real("shape_pt_lat"),
        lon=fields.real("shape_pt_lon"),
        dist=fields.optional_real("shape_dist_traveled"),
    )


def trip_record(row: GtfsRow, has_direction: bool) -> TripRecord:
    fields = _Fields("trips.txt", row)
    direction_id: int | None = None
    if has_direction:
        value = fields.raw("direction_id").strip()
        if value not in DIRECTION_IDS:
            raise fields.error("invalid direction_id")
        direction_id = int(value)
    return TripRecord(
        trip_id=fields.required("trip_id"),
        route_id=fields.required("route_id"),
        service_id=fields.required("service_id"),
        headsign=fields.name("trip_headsign") or None,
        shape_id=fields.required("shape_id"),
        direction_id=direction_id,
    )


def stop_time_record(row: GtfsRow) -> StopTimeRecord:
    fields = _Fields("stop_times.txt", row)
    return StopTimeRecord(
        trip_id=fields.required("trip_id"),
        stop_sequence=fields.integer("stop_sequence"),
        stop_id=fields.required("stop_id"),
        arrival_s=fields.time("arrival_time"),
        departure_s=fields.time("departure_time"),
        shape_dist=fields.optional_real("shape_dist_traveled"),
    )
