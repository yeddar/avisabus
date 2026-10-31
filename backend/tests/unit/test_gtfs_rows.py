from datetime import date

import pytest

from avisabus.application.errors import GtfsDataError
from avisabus.application.gtfs_rows import (
    agency_timezone,
    calendar_date_record,
    calendar_record,
    feed_info,
    route_record,
    shape_point_record,
    stop_record,
    stop_time_record,
    trip_record,
)
from avisabus.domain.models.network import CalendarException, ServiceCalendar
from avisabus.domain.ports.gtfs_import import (
    GtfsRow,
    RouteRecord,
    ShapePointRecord,
    StopRecord,
    StopTimeRecord,
    TripRecord,
)


def _row(line: int = 2, **values: str) -> GtfsRow:
    return GtfsRow(line_number=line, values=values)


@pytest.mark.spec("gtfs_import.AC-07")
def test_stop_and_route_names_are_trimmed_only_at_the_ends() -> None:
    stop = stop_record(
        _row(
            stop_id="2009",
            stop_name=" Tres Creus  - Músic Ayllón ",
            stop_lat="39.4",
            stop_lon="-0.3",
        )
    )
    assert stop == StopRecord("2009", "Tres Creus  - Músic Ayllón", 39.4, -0.3)
    route = route_record(
        _row(
            route_id="1018",
            route_short_name=" C1 ",
            route_long_name="C1 - CENTRE HISTÒRIC ",
            route_color="",
            route_text_color="",
        )
    )
    assert route == RouteRecord("1018", "C1", "C1 - CENTRE HISTÒRIC", "FE0000", "FFFFFF")


@pytest.mark.spec("gtfs_import.AC-07")
def test_trip_headsign_is_trimmed_and_empty_means_missing() -> None:
    values = {"route_id": "967", "service_id": "s", "trip_id": "t", "shape_id": "sh"}
    trip = trip_record(_row(**values, trip_headsign="Terramelar "), has_direction=False)
    assert trip == TripRecord("t", "967", "s", "Terramelar", "sh", None)
    assert trip_record(_row(**values, trip_headsign="  "), has_direction=False).headsign is None
    assert trip_record(_row(**values), has_direction=False).headsign is None


@pytest.mark.spec("gtfs_import.AC-23")
def test_trip_direction_comes_from_the_feed_when_the_column_exists() -> None:
    values = {"route_id": "r", "service_id": "s", "trip_id": "t", "shape_id": "sh"}
    assert trip_record(_row(**values, direction_id="1"), has_direction=True).direction_id == 1
    assert trip_record(_row(**values, direction_id="0"), has_direction=True).direction_id == 0
    with pytest.raises(GtfsDataError):
        trip_record(_row(**values, direction_id="2"), has_direction=True)
    with pytest.raises(GtfsDataError):
        trip_record(_row(**values, direction_id=""), has_direction=True)


def test_trip_without_shape_is_a_data_error() -> None:
    values = {"route_id": "r", "service_id": "s", "trip_id": "t", "shape_id": ""}
    with pytest.raises(GtfsDataError) as exc:
        trip_record(_row(line=7, **values), has_direction=False)
    assert (exc.value.file, exc.value.line_number) == ("trips.txt", 7)


@pytest.mark.spec("gtfs_import.AC-08")
def test_stop_times_are_stored_in_seconds_including_after_midnight() -> None:
    record = stop_time_record(
        _row(
            trip_id="t",
            arrival_time="25:10:00",
            departure_time="25:10:30",
            stop_id="508",
            stop_sequence="3",
            shape_dist_traveled="1250.5",
        )
    )
    assert record == StopTimeRecord("t", 3, "508", 90600, 90630, 1250.5)
    no_dist = stop_time_record(
        _row(
            trip_id="t",
            arrival_time="6:00:00",
            departure_time="06:00:00",
            stop_id="1",
            stop_sequence="1",
        )
    )
    assert no_dist.shape_dist is None
    assert no_dist.arrival_s == 21600


@pytest.mark.spec("gtfs_import.AC-08")
@pytest.mark.parametrize("bad", ["", "7:5:00", "aa:00:00"])
def test_invalid_stop_time_is_a_data_error_with_its_line(bad: str) -> None:
    row = _row(
        line=42,
        trip_id="t",
        arrival_time=bad,
        departure_time="06:00:00",
        stop_id="1",
        stop_sequence="1",
    )
    with pytest.raises(GtfsDataError) as exc:
        stop_time_record(row)
    assert (exc.value.file, exc.value.line_number) == ("stop_times.txt", 42)


def test_calendar_rows() -> None:
    record = calendar_record(
        _row(
            service_id="s",
            monday="1",
            tuesday="1",
            wednesday="1",
            thursday="1",
            friday="0",
            saturday="0",
            sunday="0",
            start_date="20261016",
            end_date="20261122",
        )
    )
    assert record == ServiceCalendar(
        "s", (True, True, True, True, False, False, False), date(2026, 10, 16), date(2026, 11, 22)
    )
    exception = calendar_date_record(_row(service_id="s", date="20261101", exception_type="2"))
    assert exception == CalendarException("s", date(2026, 11, 1), 2)
    with pytest.raises(GtfsDataError):
        calendar_date_record(_row(service_id="s", date="20261101", exception_type="3"))
    with pytest.raises(GtfsDataError):
        calendar_date_record(_row(service_id="s", date="2026-11-01", exception_type="1"))


def test_shape_points_and_numbers() -> None:
    point = shape_point_record(
        _row(shape_id="a", shape_pt_lat="39.1", shape_pt_lon="-0.4", shape_pt_sequence="2")
    )
    assert point == ShapePointRecord("a", 2, 39.1, -0.4, None)
    with pytest.raises(GtfsDataError) as exc:
        stop_record(_row(line=9, stop_id="1", stop_name="x", stop_lat="north", stop_lon="0"))
    assert (exc.value.file, exc.value.line_number) == ("stops.txt", 9)


def test_agency_timezone_and_feed_info() -> None:
    assert agency_timezone(_row(agency_name="EMT", agency_timezone=" Europe/Madrid")) == (
        "Europe/Madrid"
    )
    with pytest.raises(GtfsDataError):
        agency_timezone(_row(agency_name="EMT", agency_timezone="Mars/Olympus"))
    assert feed_info(
        _row(feed_version="23-10-2026", feed_start_date="20261016", feed_end_date="20261122")
    ) == ("23-10-2026", date(2026, 10, 16), date(2026, 11, 22))
    assert feed_info(_row(feed_publisher_name="EMT")) == (None, None, None)
