"""SQLite adapters of the network: feed writer (import) and repository (queries).

gtfs_import design §4.2–§5. All queries filter by `feed_version_id`; readers only see the
active version, so an import never exposes partial data.
"""

import json
from collections import defaultdict
from collections.abc import Callable, Sequence
from typing import Any

import structlog
from sqlalchemy import Connection, Engine, Table, delete, insert, select, text, update

from avisabus.adapters.outbound.persistence import network_tables as t
from avisabus.domain.models.network import CalendarException, FeedVersion, ServiceCalendar
from avisabus.domain.ports.gtfs_import import (
    DerivedSummary,
    GtfsRecord,
    RouteRecord,
    ShapePointRecord,
    StopRecord,
    StopTimeRecord,
    TripRecord,
)
from avisabus.domain.services.direction_derivation import (
    Coordinate,
    DirectionPattern,
    derive_directions,
)

log = structlog.get_logger(__name__)

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


class SqliteGtfsFeedWriter:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._route_lines: dict[int, dict[str, str]] = {}

    def begin_version(self) -> int:
        with self._engine.begin() as conn:
            result = conn.execute(insert(t.feed_version).values(is_active=0))
            version_id = result.inserted_primary_key
            assert version_id is not None  # noqa: S101 - always set by SQLite
            return int(version_id[0])

    def insert_batch(self, version_id: int, records: Sequence[GtfsRecord]) -> None:
        if not records:
            return
        table, to_row = self._mapping(version_id, records[0])
        rows = [to_row(record) for record in records]
        with self._engine.begin() as conn:
            conn.execute(insert(table), rows)

    def _mapping(
        self, version_id: int, sample: GtfsRecord
    ) -> tuple[Table, Callable[[Any], dict[str, Any]]]:
        fv = version_id
        if isinstance(sample, RouteRecord):
            return t.gtfs_route, lambda r: {
                "feed_version_id": fv,
                "route_id": r.route_id,
                "short_name": r.short_name,
                "long_name": r.long_name,
                "color": r.color,
                "text_color": r.text_color,
            }
        if isinstance(sample, StopRecord):
            return t.gtfs_stop, lambda r: {
                "feed_version_id": fv,
                "stop_id": r.stop_id,
                "name": r.name,
                "lat": r.lat,
                "lon": r.lon,
            }
        if isinstance(sample, ServiceCalendar):
            return t.gtfs_calendar, lambda r: {
                "feed_version_id": fv,
                "service_id": r.service_id,
                **dict(zip(_WEEKDAYS, r.weekdays, strict=True)),
                "start_date": r.start_date,
                "end_date": r.end_date,
            }
        if isinstance(sample, CalendarException):
            return t.gtfs_calendar_date, lambda r: {
                "feed_version_id": fv,
                "service_id": r.service_id,
                "date": r.date,
                "exception_type": r.exception_type,
            }
        if isinstance(sample, ShapePointRecord):
            return t.gtfs_shape_point, lambda r: {
                "feed_version_id": fv,
                "shape_id": r.shape_id,
                "sequence": r.sequence,
                "lat": r.lat,
                "lon": r.lon,
                "dist": r.dist,
            }
        if isinstance(sample, TripRecord):
            lines = self._lines_of_routes(version_id)
            return t.gtfs_trip, lambda r: {
                "feed_version_id": fv,
                "trip_id": r.trip_id,
                "route_id": r.route_id,
                "line": lines[r.route_id],
                "service_id": r.service_id,
                "direction_id": r.direction_id,
                "direction_source": "derived" if r.direction_id is None else "feed",
                "headsign": r.headsign,
                "shape_id": r.shape_id,
            }
        if isinstance(sample, StopTimeRecord):
            return t.gtfs_stop_time, lambda r: {
                "feed_version_id": fv,
                "trip_id": r.trip_id,
                "stop_sequence": r.stop_sequence,
                "stop_id": r.stop_id,
                "arrival_s": r.arrival_s,
                "departure_s": r.departure_s,
                "shape_dist": r.shape_dist,
            }
        raise TypeError(type(sample).__name__)

    def _lines_of_routes(self, version_id: int) -> dict[str, str]:
        if version_id not in self._route_lines:
            with self._engine.connect() as conn:
                rows = conn.execute(
                    select(t.gtfs_route.c.route_id, t.gtfs_route.c.short_name).where(
                        t.gtfs_route.c.feed_version_id == version_id
                    )
                )
                self._route_lines[version_id] = {r.route_id: r.short_name for r in rows}
        return self._route_lines[version_id]

    def build_derived(self, version_id: int, directions_from_feed: bool) -> DerivedSummary:
        params = {"v": version_id}
        with self._engine.begin() as conn:
            conn.execute(text(_FILL_HEADSIGNS), params)
            conn.execute(text(_INSERT_LINES), params)
            conn.execute(text(_INSERT_LINE_ROUTES), params)
            lines = conn.execute(
                text("SELECT COUNT(*) FROM line WHERE feed_version_id = :v"), params
            ).scalar_one()
            ignored = conn.execute(text(_COUNT_IGNORED_ROUTES), params).scalar_one()
        if not directions_from_feed:
            self._derive_directions(version_id)
        with self._engine.begin() as conn:
            for statement in (
                _INSERT_LINE_DIRECTIONS,
                _INSERT_LINE_DIRECTION_SHAPES,
                _INSERT_STOP_LINE_DIRECTIONS,
                _INSERT_STOP_LINE_HEADSIGNS,
            ):
                conn.execute(text(statement), params)
        self._route_lines.pop(version_id, None)
        return DerivedSummary(lines=int(lines), ignored_route_ids=int(ignored))

    def _derive_directions(self, version_id: int) -> None:
        with self._engine.begin() as conn:
            patterns = _load_patterns(conn, version_id)
            updates: list[dict[str, Any]] = []
            for line_name, line_patterns in sorted(patterns.items()):

                def report(shape_id: str, line_name: str = line_name) -> None:
                    log.warning("gtfs.direction_ambiguous", line=line_name, shape_id=shape_id)

                directions = derive_directions(line_patterns, on_ambiguous=report)
                updates.extend(
                    {"v": version_id, "line": line_name, "shape": shape, "d": direction}
                    for shape, direction in directions.items()
                )
            if updates:
                conn.execute(
                    text(
                        "UPDATE gtfs_trip SET direction_id = :d WHERE feed_version_id = :v "
                        "AND line = :line AND shape_id = :shape"
                    ),
                    updates,
                )

    def activate(self, feed: FeedVersion, timezone: str) -> None:
        fv = t.feed_version
        with self._engine.begin() as conn:
            conn.execute(update(fv).where(fv.c.is_active == 1).values(is_active=0))
            conn.execute(
                update(fv)
                .where(fv.c.id == feed.version_id)
                .values(
                    is_active=1,
                    feed_version=feed.feed_version,
                    imported_at=feed.imported_at.isoformat(),
                    start_date=feed.start_date,
                    end_date=feed.end_date,
                    counts_json=json.dumps(dict(feed.counts), sort_keys=True),
                    timezone=timezone,
                )
            )

    def purge_inactive(self) -> None:
        active = select(t.feed_version.c.id).where(t.feed_version.c.is_active == 1)
        with self._engine.begin() as conn:
            for table in t.VERSIONED_TABLES:
                conn.execute(delete(table).where(table.c.feed_version_id.not_in(active)))
            conn.execute(delete(t.feed_version).where(t.feed_version.c.is_active == 0))

    def discard(self, version_id: int) -> None:
        self._route_lines.pop(version_id, None)
        with self._engine.begin() as conn:
            for table in t.VERSIONED_TABLES:
                conn.execute(delete(table).where(table.c.feed_version_id == version_id))
            conn.execute(
                delete(t.feed_version).where(
                    t.feed_version.c.id == version_id, t.feed_version.c.is_active == 0
                )
            )


def _load_patterns(conn: Connection, version_id: int) -> dict[str, list[DirectionPattern]]:
    """One pattern per (line, shape_id): trip count, ends of its first trip and shape points."""
    params = {"v": version_id}
    ends: dict[str, tuple[Coordinate, Coordinate]] = {}
    for row in conn.execute(text(_PATTERN_ENDS), params):
        ends[row.trip_id] = ((row.first_lat, row.first_lon), (row.last_lat, row.last_lon))
    points: dict[str, list[Coordinate]] = defaultdict(list)
    for row in conn.execute(
        text(
            "SELECT shape_id, lat, lon FROM gtfs_shape_point WHERE feed_version_id = :v "
            "ORDER BY shape_id, sequence"
        ),
        params,
    ):
        points[row.shape_id].append((row.lat, row.lon))
    patterns: dict[str, list[DirectionPattern]] = defaultdict(list)
    for row in conn.execute(text(_PATTERNS), params):
        shape_points = tuple(points.get(row.shape_id, ()))
        first, last = ends.get(row.trip_id, _shape_ends(shape_points))
        patterns[row.line].append(
            DirectionPattern(
                shape_id=row.shape_id,
                first_stop=first,
                last_stop=last,
                shape_points=shape_points,
                trip_count=row.trips,
            )
        )
    return patterns


def _shape_ends(points: tuple[Coordinate, ...]) -> tuple[Coordinate, Coordinate]:
    """Fallback for a pattern whose trip has no stop times: ends of its shape (or nowhere)."""
    if points:
        return points[0], points[-1]
    return (0.0, 0.0), (0.0, 0.0)


# --- SQL of the derived tables (design §5). `:v` is the version being imported. ---

_FILL_HEADSIGNS = """
UPDATE gtfs_trip SET headsign = COALESCE((
    SELECT s.name FROM gtfs_stop_time st
    JOIN gtfs_stop s ON s.feed_version_id = st.feed_version_id AND s.stop_id = st.stop_id
    WHERE st.feed_version_id = gtfs_trip.feed_version_id AND st.trip_id = gtfs_trip.trip_id
    ORDER BY st.stop_sequence DESC LIMIT 1
), '')
WHERE feed_version_id = :v AND headsign IS NULL
"""

_ROUTE_TRIPS = """
SELECT r.route_id, r.short_name, r.long_name, r.color, r.text_color, c.trips,
       ROW_NUMBER() OVER (PARTITION BY r.short_name ORDER BY c.trips DESC, r.route_id) AS rank
FROM gtfs_route r
JOIN (SELECT route_id, COUNT(*) AS trips FROM gtfs_trip WHERE feed_version_id = :v
      GROUP BY route_id) c ON c.route_id = r.route_id
WHERE r.feed_version_id = :v
"""

_INSERT_LINES = f"""
INSERT INTO line (feed_version_id, short_name, long_name, color, text_color)
SELECT :v, short_name, long_name, color, text_color FROM ({_ROUTE_TRIPS}) WHERE rank = 1
"""  # noqa: S608 - constant SQL

_INSERT_LINE_ROUTES = f"""
INSERT INTO line_route (feed_version_id, route_id, short_name)
SELECT :v, route_id, short_name FROM ({_ROUTE_TRIPS})
"""  # noqa: S608 - constant SQL

_COUNT_IGNORED_ROUTES = """
SELECT COUNT(*) FROM gtfs_route r
WHERE r.feed_version_id = :v AND NOT EXISTS (
    SELECT 1 FROM gtfs_trip tr WHERE tr.feed_version_id = :v AND tr.route_id = r.route_id)
"""

_PATTERNS = """
SELECT line, shape_id, COUNT(*) AS trips, MIN(trip_id) AS trip_id
FROM gtfs_trip WHERE feed_version_id = :v GROUP BY line, shape_id
"""

_PATTERN_ENDS = f"""
SELECT p.trip_id, fs.lat AS first_lat, fs.lon AS first_lon, ls.lat AS last_lat, ls.lon AS last_lon
FROM (
    SELECT trip_id,
        (SELECT stop_id FROM gtfs_stop_time WHERE feed_version_id = :v AND trip_id = rep.trip_id
         ORDER BY stop_sequence LIMIT 1) AS first_stop,
        (SELECT stop_id FROM gtfs_stop_time WHERE feed_version_id = :v AND trip_id = rep.trip_id
         ORDER BY stop_sequence DESC LIMIT 1) AS last_stop
    FROM ({_PATTERNS}) rep
) p
JOIN gtfs_stop fs ON fs.feed_version_id = :v AND fs.stop_id = p.first_stop
JOIN gtfs_stop ls ON ls.feed_version_id = :v AND ls.stop_id = p.last_stop
"""  # noqa: S608 - constant SQL

_INSERT_LINE_DIRECTIONS = """
INSERT INTO line_direction (feed_version_id, short_name, direction_id, headsign, shape_id,
                            trip_count)
WITH headsigns AS (
    SELECT line, direction_id, headsign, ROW_NUMBER() OVER (
        PARTITION BY line, direction_id ORDER BY COUNT(*) DESC, headsign) AS rank
    FROM gtfs_trip WHERE feed_version_id = :v GROUP BY line, direction_id, headsign
),
shapes AS (
    SELECT line, direction_id, shape_id, ROW_NUMBER() OVER (
        PARTITION BY line, direction_id ORDER BY COUNT(*) DESC, shape_id) AS rank
    FROM gtfs_trip WHERE feed_version_id = :v GROUP BY line, direction_id, shape_id
),
totals AS (
    SELECT line, direction_id, COUNT(*) AS trips
    FROM gtfs_trip WHERE feed_version_id = :v GROUP BY line, direction_id
)
SELECT :v, tt.line, tt.direction_id, h.headsign, s.shape_id, tt.trips
FROM totals tt
JOIN headsigns h ON h.line = tt.line AND h.direction_id = tt.direction_id AND h.rank = 1
JOIN shapes s ON s.line = tt.line AND s.direction_id = tt.direction_id AND s.rank = 1
"""

_INSERT_LINE_DIRECTION_SHAPES = """
INSERT INTO line_direction_shape (feed_version_id, short_name, direction_id, shape_id, trip_count)
SELECT :v, line, direction_id, shape_id, COUNT(*)
FROM gtfs_trip WHERE feed_version_id = :v GROUP BY line, direction_id, shape_id
"""

_INSERT_STOP_LINE_DIRECTIONS = """
INSERT INTO stop_line_direction (feed_version_id, stop_id, short_name, direction_id)
SELECT DISTINCT :v, st.stop_id, tr.line, tr.direction_id
FROM gtfs_stop_time st
JOIN gtfs_trip tr ON tr.feed_version_id = st.feed_version_id AND tr.trip_id = st.trip_id
WHERE st.feed_version_id = :v
"""

_INSERT_STOP_LINE_HEADSIGNS = """
INSERT INTO stop_line_headsign (feed_version_id, stop_id, short_name, direction_id, headsign,
                                trip_count)
SELECT :v, st.stop_id, tr.line, tr.direction_id, tr.headsign, COUNT(DISTINCT st.trip_id)
FROM gtfs_stop_time st
JOIN gtfs_trip tr ON tr.feed_version_id = st.feed_version_id AND tr.trip_id = st.trip_id
WHERE st.feed_version_id = :v
GROUP BY st.stop_id, tr.line, tr.direction_id, tr.headsign
"""
