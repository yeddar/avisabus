"""`list_lines` and `departures` of the network over `gtfs_mini` (driver_session T-02).

Expected values are computed from the fixture CSV files; only the derived `direction_id` is read
from the database.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import Engine, text

from avisabus.adapters.outbound.persistence.sqlite_driver_sessions import (
    SqliteDriverSessionRepository,
)
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.application.driver_sessions import ListDepartures, ListDeparturesCommand
from avisabus.domain.models.driver import DriverService
from avisabus.domain.models.network import Departure
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.gtfs_time import parse_gtfs_time
from avisabus.domain.services.line_order import natural_line_key
from tests.support.drivers import session_of
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI, read_rows
from tests.support.stops import import_feed, new_engine

MONDAY = date(2026, 11, 9)
SUNDAY = date(2026, 11, 8)


@pytest.fixture(scope="module")
def mini_engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    path: Path = tmp_path_factory.mktemp("departures") / "avisabus.sqlite"
    engine = new_engine(path)
    import_feed(engine, GTFS_MINI)
    yield engine
    engine.dispose()


@pytest.fixture
def network(mini_engine: Engine) -> SqliteNetworkRepository:
    return SqliteNetworkRepository(mini_engine)


def _table(name: str) -> list[dict[str, str]]:
    header, *rows = read_rows(GTFS_MINI / name)
    return [dict(zip(header, row, strict=True)) for row in rows]


def _directions(engine: Engine) -> dict[str, tuple[str, int]]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT trip_id, line, direction_id FROM gtfs_trip"))
        return {r.trip_id: (r.line, r.direction_id) for r in rows}


def _active_services(service_date: date) -> set[str]:
    column = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")[
        service_date.weekday()
    ]
    day = service_date.strftime("%Y%m%d")
    return {
        row["service_id"]
        for row in _table("calendar.txt")
        if row[column] == "1" and row["start_date"] <= day <= row["end_date"]
    }


def _first_calls() -> dict[str, dict[str, str]]:
    first: dict[str, dict[str, str]] = {}
    for row in _table("stop_times.txt"):
        seen = first.get(row["trip_id"])
        if seen is None or int(row["stop_sequence"]) < int(seen["stop_sequence"]):
            first[row["trip_id"]] = row
    return first


def _expected(
    engine: Engine, line: str, direction_id: int, service_date: date, low: int, high: int
) -> list[Departure]:
    trips = {row["trip_id"]: row for row in _table("trips.txt")}
    stops = {row["stop_id"]: row["stop_name"] for row in _table("stops.txt")}
    active = _active_services(service_date)
    directions = _directions(engine)
    expected = []
    for trip_id, call in _first_calls().items():
        departure_s = parse_gtfs_time(call["departure_time"])
        if (
            directions[trip_id] == (line, direction_id)
            and trips[trip_id]["service_id"] in active
            and low <= departure_s <= high
        ):
            expected.append(
                Departure(
                    trip_id,
                    service_date,
                    departure_s,
                    stops[call["stop_id"]],
                    trips[trip_id]["trip_headsign"],
                )
            )
    expected.sort(key=lambda d: (d.departure_s, d.trip_id))
    return expected


def _normalised(departures: list[Departure]) -> list[tuple[str, date, int, str, str]]:
    return [
        (d.trip_id, d.service_date, d.departure_s, d.first_stop_name.strip(), d.headsign.strip())
        for d in departures
    ]


def test_repository_satisfies_the_port(network: SqliteNetworkRepository) -> None:
    port: NetworkRepository = network
    assert port.list_lines()


@pytest.mark.spec("driver_session.AC-05")
def test_list_lines_gives_every_line_in_line_order_with_its_directions(
    network: SqliteNetworkRepository, mini_engine: Engine
) -> None:
    lines = network.list_lines()
    routes = _table("routes.txt")
    assert [view.line for view in lines] == sorted(
        {route["route_short_name"] for route in routes}, key=natural_line_key
    )
    for view in lines:
        assert [d.direction_id for d in view.directions] == [0, 1]
        line = network.get_line(view.line)
        assert line is not None
        assert (view.color, view.text_color) == (line.color, line.text_color)
        expected = {d.direction_id: d.headsign for d in network.line_directions(view.line)}
        assert {d.direction_id: d.headsign for d in view.directions} == expected


@pytest.mark.spec("driver_session.AC-05")
def test_list_lines_without_a_feed_is_empty(engine: Engine) -> None:
    assert SqliteNetworkRepository(engine).list_lines() == []


@pytest.mark.spec("driver_session.AC-06")
def test_departures_of_a_morning_window_match_the_feed(
    network: SqliteNetworkRepository, mini_engine: Engine
) -> None:
    low, high = 8 * 3600, 9 * 3600
    found = network.departures("93", 0, MONDAY, low, high)
    expected = _expected(mini_engine, "93", 0, MONDAY, low, high)
    assert expected
    assert _normalised(found) == _normalised(expected)


@pytest.mark.spec("driver_session.AC-06")
def test_departures_are_only_those_of_the_direction(
    network: SqliteNetworkRepository, mini_engine: Engine
) -> None:
    low, high = 8 * 3600, 9 * 3600
    outbound = {d.trip_id for d in network.departures("93", 0, MONDAY, low, high)}
    inbound = {d.trip_id for d in network.departures("93", 1, MONDAY, low, high)}
    assert outbound and inbound
    assert not outbound & inbound


@pytest.mark.spec("driver_session.AC-06")
def test_departures_depend_on_the_active_service_of_the_day(
    network: SqliteNetworkRepository, mini_engine: Engine
) -> None:
    # The 98 has one route for working days (1054) and another one for Sundays (1055).
    low, high = 8 * 3600, 12 * 3600
    assert {d.trip_id.split("_")[1] for d in network.departures("98", 0, MONDAY, low, high)} == {
        "1054"
    }
    assert {d.trip_id.split("_")[1] for d in network.departures("98", 0, SUNDAY, low, high)} == {
        "1055"
    }


@pytest.mark.spec("driver_session.AC-06")
def test_window_is_inclusive_at_both_ends(
    network: SqliteNetworkRepository, mini_engine: Engine
) -> None:
    sample = network.departures("93", 0, MONDAY, 8 * 3600, 9 * 3600)[0]
    at_exact = network.departures("93", 0, MONDAY, sample.departure_s, sample.departure_s)
    assert sample.trip_id in {d.trip_id for d in at_exact}


@pytest.mark.spec("driver_session.AC-06")
def test_a_stop_time_that_is_not_the_first_never_counts_as_the_departure(
    network: SqliteNetworkRepository,
) -> None:
    first = _first_calls()
    for departure in network.departures("93", 0, MONDAY, 0, 200_000):
        assert parse_gtfs_time(first[departure.trip_id]["departure_time"]) == departure.departure_s


@pytest.mark.spec("driver_session.AC-06")
def test_times_past_midnight_belong_to_the_previous_service_day(
    network: SqliteNetworkRepository, mini_engine: Engine
) -> None:
    low, high = 24 * 3600, 27 * 3600
    late = _expected(mini_engine, "93", 0, MONDAY, low, high) + _expected(
        mini_engine, "93", 1, MONDAY, low, high
    )
    assert late, "gtfs_mini has trips of the 93 after 24:00 on Monday"
    found = network.departures("93", 0, MONDAY, low, high) + network.departures(
        "93", 1, MONDAY, low, high
    )
    assert {d.trip_id for d in found} == {d.trip_id for d in late}


@pytest.mark.spec("driver_session.AC-06")
async def test_use_case_lists_previous_day_trips_past_midnight(
    network: SqliteNetworkRepository, mini_engine: Engine, engine: Engine
) -> None:
    """At 00:30 of Tuesday, the 24:xx trips of Monday are offered with Monday's service date."""
    # 00:30 in Madrid of 2026-11-10 (UTC+1).
    now = datetime(2026, 11, 9, 23, 30, tzinfo=UTC)
    low = 24 * 3600 + 30 * 60 - 1800
    high = 24 * 3600 + 30 * 60 + 3600
    late = _expected(mini_engine, "93", 0, MONDAY, low, high)
    assert late

    use_case = ListDepartures(network, SqliteDriverSessionRepository(engine), FakeClock(now))
    found = await use_case.execute(ListDeparturesCommand(session_of(), "93", 0))

    previous_day = [d for d in found if d.service_date == MONDAY]
    assert {d.trip_id for d in previous_day} == {d.trip_id for d in late}
    start = datetime(2026, 11, 8, 23, 0, tzinfo=UTC)  # Monday's day start in UTC
    assert all(d.departure_at >= start + timedelta(hours=24) for d in previous_day)


@pytest.mark.spec("driver_session.AC-06")
async def test_use_case_marks_a_departure_held_by_another_real_session(
    network: SqliteNetworkRepository, mini_engine: Engine, engine: Engine
) -> None:
    now = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)
    sessions = SqliteDriverSessionRepository(engine)
    use_case = ListDepartures(network, sessions, FakeClock(now))
    command = ListDeparturesCommand(session_of(1), "93", 0)

    trip = (await use_case.execute(command))[0]
    assert trip.taken is False
    sessions.add(session_of(2, DriverService("93", 0, trip.trip_id, trip.service_date)))

    assert (await use_case.execute(command))[0].taken is True


def test_departures_are_empty_without_a_feed(engine: Engine) -> None:
    assert SqliteNetworkRepository(engine).departures("93", 0, MONDAY, 0, 86400) == []


def test_departures_of_an_unknown_line_are_empty(network: SqliteNetworkRepository) -> None:
    assert network.departures("nope", 0, MONDAY, 0, 86400) == []
