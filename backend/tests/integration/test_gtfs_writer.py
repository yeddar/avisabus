from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine, text

from avisabus.adapters.outbound.persistence.network_tables import VERSIONED_TABLES
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteGtfsFeedWriter
from avisabus.domain.models.network import FeedVersion
from tests.support.gtfs import (
    InjectedFailureError,
    add_column,
    append_rows,
    copy_gtfs_mini,
    drop_column,
    load_feed,
    read_rows,
    write_rows,
)

LINES = ("70", "93", "98", "C2")


@pytest.fixture
def writer(engine: Engine) -> SqliteGtfsFeedWriter:
    return SqliteGtfsFeedWriter(engine)


@pytest.fixture
def feed_dir(tmp_path: Path) -> Path:
    return copy_gtfs_mini(tmp_path / "feed")


def _activate(writer: SqliteGtfsFeedWriter, version_id: int) -> None:
    writer.activate(
        FeedVersion(
            version_id=version_id,
            feed_version="23-10-2026",
            imported_at=datetime(2026, 10, 31, 8, 0, tzinfo=UTC),
            start_date=date(2026, 10, 16),
            end_date=date(2026, 11, 22),
            counts={"stops": 178},
        ),
        "Europe/Madrid",
    )


def _import(writer: SqliteGtfsFeedWriter, feed_dir: Path) -> int:
    version_id = load_feed(writer, feed_dir)
    _activate(writer, version_id)
    writer.purge_inactive()
    return version_id


def _rows(engine: Engine, sql: str, **params: Any) -> list[Any]:
    with engine.connect() as conn:
        return list(conn.execute(text(sql), params))


def _versions_in(engine: Engine) -> dict[str, set[int]]:
    result: dict[str, set[int]] = {}
    for table in VERSIONED_TABLES:
        rows = _rows(engine, f"SELECT DISTINCT feed_version_id FROM {table.name}")  # noqa: S608
        result[table.name] = {r[0] for r in rows}
    return result


def _trip_directions(engine: Engine, version_id: int) -> dict[str, tuple[int, str]]:
    rows = _rows(
        engine,
        "SELECT shape_id, direction_id, direction_source FROM gtfs_trip "
        "WHERE feed_version_id = :v GROUP BY shape_id, direction_id, direction_source",
        v=version_id,
    )
    shapes = Counter(r[0] for r in rows)
    assert all(n == 1 for n in shapes.values()), "a shape with two directions"
    return {r[0]: (r[1], r[2]) for r in rows}


def test_imports_every_row_of_gtfs_mini(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    version_id = _import(writer, feed_dir)
    counts = {
        name: _rows(
            engine,
            f"SELECT COUNT(*) FROM {name} WHERE feed_version_id = :v",  # noqa: S608
            v=version_id,
        )[0][0]
        for name in (
            "gtfs_route",
            "gtfs_stop",
            "gtfs_trip",
            "gtfs_stop_time",
            "gtfs_shape_point",
            "gtfs_calendar",
        )
    }
    assert counts == {
        "gtfs_route": 6,
        "gtfs_stop": 178,
        "gtfs_trip": 1109,
        "gtfs_stop_time": 29040,
        "gtfs_shape_point": 2882,
        "gtfs_calendar": 8,
    }
    (row,) = _rows(engine, "SELECT is_active, feed_version, timezone FROM feed_version")
    assert tuple(row) == (1, "23-10-2026", "Europe/Madrid")


@pytest.mark.spec("gtfs_import.AC-06")
def test_second_import_activates_new_version_and_purges_the_previous(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    first = _import(writer, feed_dir)
    second = _import(writer, feed_dir)
    assert second != first
    assert [tuple(r) for r in _rows(engine, "SELECT id, is_active FROM feed_version")] == [
        (second, 1)
    ]
    versions = _versions_in(engine)
    assert versions.pop("gtfs_calendar_date") == set()  # gtfs_mini has no calendar_dates rows
    assert all(found == {second} for found in versions.values())


@pytest.mark.spec("gtfs_import.AC-06")
def test_new_version_is_invisible_until_activated(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    first = _import(writer, feed_dir)
    pending = load_feed(writer, feed_dir)
    active = _rows(engine, "SELECT id FROM feed_version WHERE is_active = 1")
    assert [r[0] for r in active] == [first]
    _activate(writer, pending)
    active = _rows(engine, "SELECT id FROM feed_version WHERE is_active = 1")
    assert [r[0] for r in active] == [pending]


@pytest.mark.spec("gtfs_import.AC-05")
def test_discard_removes_partial_data_and_keeps_previous_version_complete(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    first = _import(writer, feed_dir)
    before = _versions_in(engine)
    with pytest.raises(InjectedFailureError):
        load_feed(writer, feed_dir, fail_in="stop_times.txt")
    (failed,) = [r[0] for r in _rows(engine, "SELECT id FROM feed_version WHERE is_active = 0")]
    assert (
        _rows(engine, "SELECT COUNT(*) FROM gtfs_stop_time WHERE feed_version_id = :v", v=failed)[
            0
        ][0]
        == 1000
    )
    writer.discard(failed)
    assert _versions_in(engine) == before
    assert [tuple(r) for r in _rows(engine, "SELECT id, is_active FROM feed_version")] == [
        (first, 1)
    ]
    stop_times = _rows(
        engine, "SELECT COUNT(*) FROM gtfs_stop_time WHERE feed_version_id = :v", v=first
    )
    assert stop_times[0][0] == 29040


@pytest.mark.spec("gtfs_import.AC-09")
def test_routes_are_grouped_by_short_name_with_attributes_of_busiest_route(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    # C2: 651 has 110 trips and 996 has 105; 98: 1054 has 140 and 1055 has 67.
    rows = read_rows(feed_dir / "routes.txt")
    header = rows[0]
    for row in rows[1:]:
        values = dict(zip(header, row, strict=True))
        colors = {"651": "0000AA", "996": "00AA00", "1054": "111111", "1055": "222222"}
        if values["route_id"] in colors:
            row[header.index("route_color")] = colors[values["route_id"]]
            row[header.index("route_long_name")] = (
                f"{values['route_long_name']} #{values['route_id']}"
            )
    write_rows(feed_dir / "routes.txt", rows)
    version_id = _import(writer, feed_dir)
    lines = {
        r[0]: (r[1], r[2])
        for r in _rows(
            engine,
            "SELECT short_name, long_name, color FROM line WHERE feed_version_id = :v",
            v=version_id,
        )
    }
    assert set(lines) == set(LINES)
    assert lines["C2"] == ("C2 - CIRCULAR GRANS VIES #651", "0000AA")
    assert lines["98"] == ("98 - AV. DEL CID - EST. CABANYAL/PG. MARÍTIM #1054", "111111")
    routes = _rows(
        engine,
        "SELECT short_name, group_concat(route_id) FROM "
        "(SELECT * FROM line_route WHERE feed_version_id = :v ORDER BY route_id) "
        "GROUP BY short_name",
        v=version_id,
    )
    assert dict((r[0], r[1]) for r in routes) == {
        "70": "1058",
        "93": "994",
        "98": "1054,1055",
        "C2": "651,996",
    }


@pytest.mark.spec("gtfs_import.AC-10")
def test_line_direction_has_most_frequent_headsign_and_shape(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    version_id = _import(writer, feed_dir)
    rows = _rows(
        engine,
        "SELECT short_name, direction_id, headsign, shape_id, trip_count FROM line_direction "
        "WHERE feed_version_id = :v",
        v=version_id,
    )
    got = {(r[0], r[1]): (r[2], r[3], r[4]) for r in rows}
    assert got[("98", 0)] == ("Estació del Cabanyal", "1054_487_2229", 106)
    assert got[("98", 1)] == ("Cid - Pere Maria Orts", "1054_2229_487", 101)
    assert got[("C2", 0)] == ("Plaça d'Espanya - Ermita", "651_166_691", 108)
    assert got[("70", 0)] == ("La Fontsanta", "1058_2030_500", 145)
    assert len(got) == 8


@pytest.mark.spec("gtfs_import.AC-10")
def test_headsign_ties_are_broken_alphabetically(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    # Give line 70 direction 0 two headsigns with the same number of trips.
    rows = read_rows(feed_dir / "trips.txt")
    header = rows[0]
    shape, headsign = header.index("shape_id"), header.index("trip_headsign")
    # 145 trips: 72 "B Fontsanta" first, then 72 "A Fontsanta" and one "C Fontsanta".
    seen = 0
    for row in rows[1:]:
        if row[shape] == "1058_2030_500":
            row[headsign] = "B Fontsanta" if seen < 72 else "A Fontsanta" if seen < 144 else "C"
            seen += 1
    assert seen == 145
    write_rows(feed_dir / "trips.txt", rows)
    version_id = _import(writer, feed_dir)
    (row,) = _rows(
        engine,
        "SELECT headsign FROM line_direction WHERE feed_version_id = :v AND short_name = '70' "
        "AND direction_id = 0",
        v=version_id,
    )
    assert row[0] == "A Fontsanta"


@pytest.mark.spec("gtfs_import.AC-07")
def test_missing_headsign_uses_trimmed_name_of_last_stop(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    drop_column(feed_dir / "trips.txt", "trip_headsign")
    # Last stop of 1058_500_2030 is 2030; give it surrounding spaces.
    rows = read_rows(feed_dir / "stops.txt")
    header = rows[0]
    for row in rows[1:]:
        if row[header.index("stop_id")] == "2030":
            row[header.index("stop_name")] = f"  {row[header.index('stop_name')]} "
    write_rows(feed_dir / "stops.txt", rows)
    version_id = _import(writer, feed_dir)
    headsigns = {
        r[0]: r[1]
        for r in _rows(
            engine,
            "SELECT DISTINCT shape_id, headsign FROM gtfs_trip WHERE feed_version_id = :v",
            v=version_id,
        )
    }
    assert headsigns["1058_500_2030"] == "Alboraia"
    assert headsigns["1058_2030_500"] == "La Fontsanta"
    stop_names = {
        r[0]: r[1]
        for r in _rows(
            engine, "SELECT stop_id, name FROM gtfs_stop WHERE feed_version_id = :v", v=version_id
        )
    }
    assert stop_names["2009"] == "Tres Creus - Músic Ayllón"
    assert stop_names["1551"] == "Tarongers (imparell)  - Metro La Cadena"


@pytest.mark.spec("gtfs_import.AC-11")
def test_stop_line_directions_are_precomputed(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    version_id = _import(writer, feed_dir)
    rows = _rows(
        engine,
        "SELECT stop_id, short_name, direction_id FROM stop_line_direction "
        "WHERE feed_version_id = :v",
        v=version_id,
    )
    by_stop: dict[str, set[tuple[str, int]]] = {}
    for stop_id, line, direction in rows:
        by_stop.setdefault(stop_id, set()).add((line, direction))
    assert {line for line, _ in by_stop["508"]} == {"70", "93"}
    assert {line for line, _ in by_stop["2070"]} == {"98"}
    expected = _rows(
        engine,
        "SELECT DISTINCT st.stop_id, t.line, t.direction_id FROM gtfs_stop_time st "
        "JOIN gtfs_trip t ON t.feed_version_id = st.feed_version_id AND t.trip_id = st.trip_id "
        "WHERE st.feed_version_id = :v",
        v=version_id,
    )
    assert {tuple(r) for r in rows} == {tuple(r) for r in expected}


@pytest.mark.spec("gtfs_import.AC-24")
def test_directions_are_derived_for_gtfs_mini(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    version_id = _import(writer, feed_dir)
    directions = _trip_directions(engine, version_id)
    assert {source for _, source in directions.values()} == {"derived"}
    per_line = _rows(
        engine,
        "SELECT line, COUNT(DISTINCT direction_id) FROM gtfs_trip WHERE feed_version_id = :v "
        "GROUP BY line",
        v=version_id,
    )
    assert dict((r[0], r[1]) for r in per_line) == dict.fromkeys(LINES, 2)
    # 98: the short variant runs in the same direction as the full route.
    assert directions["1054_487_2229"][0] == directions["1055_487_2271"][0] == 0
    assert directions["1054_2229_487"][0] == directions["1055_2271_487"][0] == 1
    # C2: each direction mixes half loops of both route_ids.
    assert directions["651_166_691"][0] == directions["996_1057_346"][0] == 0
    assert directions["651_691_166"][0] == directions["996_346_1057"][0] == 1
    c2_routes = _rows(
        engine,
        "SELECT direction_id, COUNT(DISTINCT route_id) FROM gtfs_trip "
        "WHERE feed_version_id = :v AND line = 'C2' GROUP BY direction_id",
        v=version_id,
    )
    assert dict((r[0], r[1]) for r in c2_routes) == {0: 2, 1: 2}
    # Most frequent pattern of each line is direction 0.
    assert directions["1058_2030_500"][0] == 0
    assert directions["994_488_2271"][0] == 0


@pytest.mark.spec("gtfs_import.AC-23")
def test_direction_id_from_the_feed_is_used_as_is(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    # Opposite of what the derivation would give, to prove the feed wins.
    feed_directions = {
        "1058_2030_500": "1",
        "1058_500_2030": "0",
        "994_488_2271": "1",
        "994_2271_488": "0",
        "1054_487_2229": "1",
        "1055_487_2271": "1",
        "1054_2229_487": "0",
        "1055_2271_487": "0",
        "651_166_691": "1",
        "996_1057_346": "1",
        "651_691_166": "0",
        "996_346_1057": "0",
    }
    add_column(feed_dir / "trips.txt", "direction_id", feed_directions, key="shape_id")
    version_id = _import(writer, feed_dir)
    directions = _trip_directions(engine, version_id)
    assert {shape: str(d) for shape, (d, _) in directions.items()} == feed_directions
    assert {source for _, source in directions.values()} == {"feed"}


@pytest.mark.spec("gtfs_import.AC-28")
def test_routes_without_trips_are_ignored_and_counted(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    header = read_rows(feed_dir / "routes.txt")[0]

    def route(route_id: str, short_name: str) -> list[str]:
        values = {"route_id": route_id, "agency_id": "EMT", "route_short_name": short_name}
        values |= {"route_long_name": f"{short_name} - SENSE VIATGES", "route_type": "3"}
        return [values.get(column, "") for column in header]

    append_rows(feed_dir / "routes.txt", [route("9001", "23"), route("9002", "70")])
    version_id = load_feed(writer, feed_dir, derive=False)
    summary = writer.build_derived(version_id, directions_from_feed=False)
    assert summary.ignored_route_ids == 2
    assert summary.lines == 4
    lines = _rows(engine, "SELECT short_name FROM line WHERE feed_version_id = :v", v=version_id)
    assert {r[0] for r in lines} == set(LINES)
    routes = _rows(
        engine, "SELECT route_id FROM line_route WHERE feed_version_id = :v", v=version_id
    )
    assert "9001" not in {r[0] for r in routes}
    assert "9002" not in {r[0] for r in routes}


@pytest.mark.spec("gtfs_import.AC-29")
def test_every_shape_of_a_direction_is_stored_with_its_trip_count(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    version_id = _import(writer, feed_dir)
    rows = _rows(
        engine,
        "SELECT short_name, direction_id, shape_id, trip_count FROM line_direction_shape "
        "WHERE feed_version_id = :v",
        v=version_id,
    )
    got: dict[tuple[str, int], dict[str, int]] = {}
    for line, direction, shape, count in rows:
        got.setdefault((line, direction), {})[shape] = count
    assert got[("98", 0)] == {"1054_487_2229": 71, "1055_487_2271": 35}
    assert got[("98", 1)] == {"1054_2229_487": 69, "1055_2271_487": 32}
    assert got[("C2", 0)] == {"651_166_691": 56, "996_1057_346": 52}
    assert got[("C2", 1)] == {"651_691_166": 54, "996_346_1057": 53}
    assert got[("70", 0)] == {"1058_2030_500": 145}


@pytest.mark.spec("gtfs_import.AC-27")
def test_stop_line_headsigns_count_trips(
    writer: SqliteGtfsFeedWriter, engine: Engine, feed_dir: Path
) -> None:
    version_id = _import(writer, feed_dir)
    rows = _rows(
        engine,
        "SELECT direction_id, headsign, trip_count FROM stop_line_headsign "
        "WHERE feed_version_id = :v AND stop_id = '2070' AND short_name = '98'",
        v=version_id,
    )
    expected = _rows(
        engine,
        "SELECT t.direction_id, t.headsign, COUNT(DISTINCT t.trip_id) FROM gtfs_stop_time st "
        "JOIN gtfs_trip t ON t.feed_version_id = st.feed_version_id AND t.trip_id = st.trip_id "
        "WHERE st.feed_version_id = :v AND st.stop_id = '2070' AND t.line = '98' "
        "GROUP BY t.direction_id, t.headsign",
        v=version_id,
    )
    assert rows
    assert {tuple(r) for r in rows} == {tuple(r) for r in expected}
