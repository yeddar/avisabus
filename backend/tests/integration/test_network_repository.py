"""`SqliteNetworkRepository` over `gtfs_mini` (imported once per module).

Expected values are computed from the fixture CSV files, independently of the repository.
"""

import asyncio
import csv
from collections import Counter, defaultdict
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine

from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_network import (
    SqliteGtfsFeedWriter,
    SqliteNetworkRepository,
)
from avisabus.application.import_gtfs_feed import ImportGtfsFeed, ImportGtfsFeedCommand
from avisabus.config import Settings
from avisabus.domain.models.network import (
    FeedVersion,
    HeadsignAtStop,
    Line,
    ScheduledStopTime,
    ShapePoint,
    Stop,
    TripStopTime,
)
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.gtfs_time import parse_gtfs_time
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI, append_rows, copy_gtfs_mini, read_rows, write_rows

MADRID = ZoneInfo("Europe/Madrid")
IMPORTED_AT = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)


def _engine(path: Path) -> Engine:
    settings = Settings(_env_file=None, env="test", database_url=f"sqlite:///{path}")  # type: ignore[call-arg]
    engine = create_engine(settings)
    init_db(engine)
    return engine


async def _import(engine: Engine, feed: Path) -> None:
    use_case = ImportGtfsFeed(
        CsvGtfsFeedReader, SqliteGtfsFeedWriter(engine), FakeClock(IMPORTED_AT)
    )
    await use_case.execute(ImportGtfsFeedCommand(feed))


@pytest.fixture(scope="module")
def mini_engine(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Engine]:
    engine = _engine(tmp_path_factory.mktemp("repo") / "avisabus.sqlite")
    asyncio.run(_import(engine, GTFS_MINI))
    yield engine
    engine.dispose()


@pytest.fixture
def repo(mini_engine: Engine) -> SqliteNetworkRepository:
    return SqliteNetworkRepository(mini_engine)


def _csv(name: str) -> list[dict[str, str]]:
    with (GTFS_MINI / name).open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


TRIPS = {row["trip_id"]: row for row in _csv("trips.txt")}
ROUTE_LINES = {row["route_id"]: row["route_short_name"] for row in _csv("routes.txt")}
STOP_TIMES = _csv("stop_times.txt")


def test_repository_satisfies_the_port(repo: SqliteNetworkRepository) -> None:
    port: NetworkRepository = repo
    assert port.active_feed() is not None


def test_active_feed_is_the_imported_version(repo: SqliteNetworkRepository) -> None:
    feed = repo.active_feed()
    assert isinstance(feed, FeedVersion)
    assert feed.feed_version == "23-10-2026"
    assert feed.imported_at == IMPORTED_AT
    assert (feed.start_date, feed.end_date) == (date(2026, 10, 16), date(2026, 11, 22))
    assert feed.counts == {
        "lines": 4,
        "stops": 178,
        "trips": 1109,
        "stop_times": 29040,
        "ignored_route_ids": 0,
    }


def test_empty_database_has_no_active_feed(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "empty.sqlite")
    repo = SqliteNetworkRepository(engine)
    assert repo.active_feed() is None
    assert repo.get_stop("508") is None
    assert repo.lines_at_stop("508") == []
    engine.dispose()


@pytest.mark.spec("gtfs_import.AC-12")
def test_get_stop_returns_id_name_and_coordinates(repo: SqliteNetworkRepository) -> None:
    stop = repo.get_stop("508")
    expected = next(row for row in _csv("stops.txt") if row["stop_id"] == "508")
    assert stop == Stop(
        "508", "Parc de l'Oest - Enguera", float(expected["stop_lat"]), float(expected["stop_lon"])
    )
    trimmed = repo.get_stop("2009")
    assert trimmed is not None
    assert trimmed.name == "Tres Creus - Músic Ayllón"


@pytest.mark.spec("gtfs_import.AC-12")
def test_get_unknown_stop_returns_none(repo: SqliteNetworkRepository) -> None:
    assert repo.get_stop("999999") is None


def test_list_stop_ids(repo: SqliteNetworkRepository) -> None:
    ids = repo.list_stop_ids()
    assert len(ids) == 178
    assert "508" in ids
    assert "2070" in ids


def test_get_line_groups_its_route_ids(repo: SqliteNetworkRepository) -> None:
    assert repo.get_line("C2") == Line(
        "C2", "C2 - CIRCULAR GRANS VIES", "FE0000", "FFFFFF", frozenset({"651", "996"})
    )
    assert repo.get_line("23") is None


@pytest.mark.spec("gtfs_import.AC-13")
def test_lines_at_stop_are_in_natural_order_with_direction_and_colors(
    repo: SqliteNetworkRepository,
) -> None:
    at_508 = repo.lines_at_stop("508")
    assert [(d.line, d.direction_id) for d in at_508] == sorted(
        {(d.line, d.direction_id) for d in at_508}, key=lambda p: (int(p[0]), p[1])
    )
    assert {d.line for d in at_508} == {"70", "93"}
    for direction in at_508:
        main = repo.line_direction(direction.line, direction.direction_id)
        assert direction == main
        assert (direction.color, direction.text_color) == ("FE0000", "FFFFFF")
    # Numeric lines first, then alphanumeric ones.
    at_223 = repo.lines_at_stop("223")
    assert [d.line for d in at_223][0] in {"70", "93"}
    assert [d.line for d in at_223][-1] == "C2"


@pytest.mark.spec("gtfs_import.AC-27")
def test_headsigns_at_stop_count_trips_per_direction_and_headsign(
    repo: SqliteNetworkRepository,
) -> None:
    expected: Counter[tuple[str, str]] = Counter()
    for row in STOP_TIMES:
        trip = TRIPS[row["trip_id"]]
        if row["stop_id"] == "2070" and ROUTE_LINES[trip["route_id"]] == "98":
            expected[(trip["shape_id"], trip["trip_headsign"].strip())] += 1
    shapes = {shape: d for d in (0, 1) for shape, _ in repo.shapes_for_direction("98", d)}
    by_direction: Counter[tuple[int, str]] = Counter()
    for (shape, headsign), n in expected.items():
        by_direction[(shapes[shape], headsign)] += n
    got = repo.headsigns_at_stop("2070", "98")
    assert {(h.direction_id, h.headsign): h.trip_count for h in got} == dict(by_direction)
    assert all(isinstance(h, HeadsignAtStop) and h.line == "98" for h in got)
    assert [(h.direction_id, -h.trip_count) for h in got] == sorted(
        (h.direction_id, -h.trip_count) for h in got
    )
    assert repo.headsigns_at_stop("2070", "70") == []


@pytest.mark.spec("gtfs_import.AC-29")
def test_shapes_for_direction_are_sorted_by_trip_count(repo: SqliteNetworkRepository) -> None:
    assert repo.shapes_for_direction("98", 0) == [("1054_487_2229", 71), ("1055_487_2271", 35)]
    assert repo.shapes_for_direction("98", 1) == [("1054_2229_487", 69), ("1055_2271_487", 32)]
    assert repo.shapes_for_direction("C2", 0) == [("651_166_691", 56), ("996_1057_346", 52)]
    assert repo.shapes_for_direction("C2", 1) == [("651_691_166", 54), ("996_346_1057", 53)]
    assert repo.shapes_for_direction("70", 2) == []


def test_line_directions(repo: SqliteNetworkRepository) -> None:
    directions = repo.line_directions("93")
    assert [d.direction_id for d in directions] == [0, 1]
    assert directions[0].headsign == "Passeig Marítim - Hospital Malva-rosa"
    assert directions[0].shape_id == "994_488_2271"
    assert repo.line_direction("93", 5) is None


@pytest.mark.spec("gtfs_import.AC-14")
def test_active_service_ids_by_weekday_and_range(repo: SqliteNetworkRepository) -> None:
    monday = {"38_1054_561", "70_1058_601", "79_996_601", "80_651_601", "93_994_561"}
    assert repo.active_service_ids(date(2026, 11, 9)) == monday
    friday = {"38_1054_561", "79_996_601", "80_651_601"}
    assert repo.active_service_ids(date(2026, 11, 13)) == friday
    sunday = {"38_1055_604", "70_1058_609", "93_994_604"}
    assert repo.active_service_ids(date(2026, 11, 8)) == sunday
    assert repo.active_service_ids(date(2026, 11, 23)) == frozenset()


@pytest.mark.spec("gtfs_import.AC-14")
async def test_active_service_ids_apply_calendar_dates(tmp_path: Path) -> None:
    feed = copy_gtfs_mini(tmp_path / "feed")
    append_rows(
        feed / "calendar_dates.txt",
        [["70_1058_601", "20261110", "2"], ["70_1058_609", "20261110", "1"]],
    )
    engine = _engine(tmp_path / "db.sqlite")
    await _import(engine, feed)
    repo = SqliteNetworkRepository(engine)
    tuesday = repo.active_service_ids(date(2026, 11, 10))
    assert "70_1058_601" not in tuesday
    assert "70_1058_609" in tuesday
    assert "70_1058_601" in repo.active_service_ids(date(2026, 11, 11))
    engine.dispose()


def _expected_passages(
    stop_id: str, at: datetime, window: timedelta
) -> list[tuple[str, date, int]]:
    """Brute force over the CSV: (trip_id, service_date, arrival_s) inside the window."""
    services = {
        date(2026, 11, 8): {"38_1055_604", "70_1058_609", "93_994_604"},
        date(2026, 11, 9): {"38_1054_561", "70_1058_601", "79_996_601", "80_651_601", "93_994_561"},
    }
    result = []
    for row in STOP_TIMES:
        if row["stop_id"] != stop_id:
            continue
        trip = TRIPS[row["trip_id"]]
        for service_date, active in services.items():
            if trip["service_id"] not in active:
                continue
            noon = datetime(
                service_date.year, service_date.month, service_date.day, 12, tzinfo=MADRID
            )
            when = noon.astimezone(UTC) - timedelta(hours=12)
            arrival_s = parse_gtfs_time(row["arrival_time"])
            if at <= when + timedelta(seconds=arrival_s) <= at + window:
                result.append((row["trip_id"], service_date, arrival_s))
    return sorted(result, key=lambda r: (r[1], r[2]))


@pytest.mark.spec("gtfs_import.AC-15")
def test_scheduled_stop_times_after_midnight_include_previous_service_day(
    repo: SqliteNetworkRepository,
) -> None:
    # Monday 2026-11-09 at 00:00 in València: Sunday trips still run (hours >= 24:00).
    at = datetime(2026, 11, 9, 0, 0, tzinfo=MADRID)
    window = timedelta(hours=2)
    got = repo.scheduled_stop_times("508", at, window)
    expected = _expected_passages("508", at, window)
    assert [(s.trip_id, s.service_date, s.arrival_s) for s in got] == expected
    sunday = [s for s in got if s.service_date == date(2026, 11, 8)]
    assert sunday
    assert all(s.arrival_s >= 86400 for s in sunday)
    assert {s.line for s in got} == {"70", "93"}
    first = got[0]
    assert isinstance(first, ScheduledStopTime)
    trip = TRIPS[first.trip_id]
    assert first.headsign == trip["trip_headsign"].strip()
    assert first.direction_id in (0, 1)


@pytest.mark.spec("gtfs_import.AC-15")
def test_scheduled_stop_times_during_the_day_use_only_active_services(
    repo: SqliteNetworkRepository,
) -> None:
    at = datetime(2026, 11, 9, 8, 0, tzinfo=MADRID).astimezone(UTC)
    window = timedelta(minutes=30)
    got = repo.scheduled_stop_times("508", at, window)
    assert got
    assert [(s.trip_id, s.service_date, s.arrival_s) for s in got] == _expected_passages(
        "508", at, window
    )
    assert {TRIPS[s.trip_id]["service_id"] for s in got} <= {"70_1058_601", "93_994_561"}
    assert all(28800 <= s.arrival_s <= 30600 for s in got)


@pytest.mark.spec("gtfs_import.AC-15")
def test_scheduled_stop_times_on_dst_change_day_count_from_noon_minus_12h(
    repo: SqliteNetworkRepository,
) -> None:
    # 2026-10-25 (Sunday) clocks go back at 03:00. The service day starts at 23:00 UTC of the
    # 24th (noon CET - 12 h), so 08:00 CET is 8 h after it.
    at = datetime(2026, 10, 25, 8, 0, tzinfo=MADRID)
    got = repo.scheduled_stop_times("508", at, timedelta(minutes=30))
    today = [s for s in got if s.service_date == date(2026, 10, 25)]
    assert today
    assert all(28800 <= s.arrival_s <= 30600 for s in today)


@pytest.mark.spec("gtfs_import.AC-16")
def test_trip_stop_times_are_ordered_by_sequence(repo: SqliteNetworkRepository) -> None:
    trip_id = next(t for t, row in TRIPS.items() if row["shape_id"] == "1054_487_2229")
    rows = sorted(
        (r for r in STOP_TIMES if r["trip_id"] == trip_id), key=lambda r: int(r["stop_sequence"])
    )
    got = repo.trip_stop_times(trip_id)
    assert got == [
        TripStopTime(
            r["stop_id"],
            int(r["stop_sequence"]),
            parse_gtfs_time(r["arrival_time"]),
            parse_gtfs_time(r["departure_time"]),
            float(r["shape_dist_traveled"]),
        )
        for r in rows
    ]
    assert got[0].shape_dist_traveled == 0.0
    assert repo.trip_stop_times("ghost") == []


@pytest.mark.spec("gtfs_import.AC-17")
def test_shape_of_a_line_direction_is_its_representative_shape_in_order(
    repo: SqliteNetworkRepository,
) -> None:
    direction = repo.line_direction("98", 0)
    assert direction is not None
    points = repo.shape_points(direction.shape_id)
    expected: dict[int, ShapePoint] = {}
    for row in _csv("shapes.txt"):
        if row["shape_id"] == direction.shape_id:
            dist = float(row["shape_dist_traveled"]) if row["shape_dist_traveled"] else None
            seq = int(row["shape_pt_sequence"])
            expected[seq] = ShapePoint(
                float(row["shape_pt_lat"]), float(row["shape_pt_lon"]), seq, dist
            )
    assert points == [expected[seq] for seq in sorted(expected)]
    assert repo.shape_points("ghost") == []


def test_direction_report_lists_every_line_direction(repo: SqliteNetworkRepository) -> None:
    report = repo.direction_report()
    assert [(r.line, r.direction_id) for r in report] == [
        (line, d) for line in ("70", "93", "98", "C2") for d in (0, 1)
    ]
    r98 = report[4]
    assert r98.source == "derived"
    assert r98.main_shape_id == "1054_487_2229"
    assert (r98.first_stop.stop_id, r98.last_stop.stop_id) == ("487", "2229")
    assert r98.headsigns == (
        ("Estació del Cabanyal", 71),
        ("Passeig Marítim - Hospital Malva-rosa", 35),
    )
    assert r98.patterns == (("1054_487_2229", 71), ("1055_487_2271", 35))
    assert r98.trip_count == 106
    counts: defaultdict[str, int] = defaultdict(int)
    for r in report:
        counts[r.line] += r.trip_count
    assert sum(counts.values()) == 1109


# --- trip_line (port extension defined by occupancy_sensor design §3, "Forzado") ---


def test_trip_line_is_the_commercial_line_of_every_trip(repo: SqliteNetworkRepository) -> None:
    port: NetworkRepository = repo
    for trip_id, row in TRIPS.items():
        assert port.trip_line(trip_id) == ROUTE_LINES[row["route_id"]]


def test_trip_line_groups_route_ids_by_short_name(repo: SqliteNetworkRepository) -> None:
    c2_routes = {route for route, line in ROUTE_LINES.items() if line == "C2"}
    assert len(c2_routes) > 1
    c2_trips = [t for t, row in TRIPS.items() if row["route_id"] in c2_routes]
    assert {repo.trip_line(t) for t in c2_trips} == {"C2"}
    assert {TRIPS[t]["route_id"] for t in c2_trips} == c2_routes


def test_trip_line_of_an_unknown_trip_is_none(repo: SqliteNetworkRepository) -> None:
    assert repo.trip_line("ghost") is None


def test_trip_line_without_an_active_feed_is_none(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "empty.sqlite")
    assert SqliteNetworkRepository(engine).trip_line(next(iter(TRIPS))) is None
    engine.dispose()


async def test_trip_line_only_sees_the_active_feed_version(tmp_path: Path) -> None:
    engine = _engine(tmp_path / "reimport.sqlite")
    feed = copy_gtfs_mini(tmp_path / "feed")
    await _import(engine, feed)
    trip_id, row = next(iter(TRIPS.items()))
    for name, column in (("trips.txt", "trip_id"), ("stop_times.txt", "trip_id")):
        header, *rows = read_rows(feed / name)
        index = header.index(column)
        write_rows(feed / name, [header, *(r for r in rows if r[index] != trip_id)])
    repo = SqliteNetworkRepository(engine)
    assert repo.trip_line(trip_id) == ROUTE_LINES[row["route_id"]]
    await _import(engine, feed)
    assert repo.trip_line(trip_id) is None
    engine.dispose()
