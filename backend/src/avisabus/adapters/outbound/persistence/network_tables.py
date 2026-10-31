"""SQLAlchemy Core tables of the transport network (gtfs_import design §4.2).

Every data table carries `feed_version_id`; readers only see the active version.
"""

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)

metadata = MetaData()


def _fv() -> Column[int]:
    return Column("feed_version_id", Integer, primary_key=True, nullable=False)


feed_version = Table(
    "feed_version",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("feed_version", String),
    Column("imported_at", String),  # ISO 8601 in UTC
    Column("start_date", Date),
    Column("end_date", Date),
    Column("is_active", Integer, nullable=False, server_default=text("0")),
    Column("counts_json", Text),
    Column("timezone", String),
    Index("ux_feed_version_active", "is_active", unique=True, sqlite_where=text("is_active = 1")),
    sqlite_autoincrement=True,
)

gtfs_stop = Table(
    "gtfs_stop",
    metadata,
    _fv(),
    Column("stop_id", String, primary_key=True),
    Column("name", String, nullable=False),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
)

gtfs_route = Table(
    "gtfs_route",
    metadata,
    _fv(),
    Column("route_id", String, primary_key=True),
    Column("short_name", String, nullable=False),
    Column("long_name", String, nullable=False),
    Column("color", String, nullable=False),
    Column("text_color", String, nullable=False),
)

gtfs_trip = Table(
    "gtfs_trip",
    metadata,
    _fv(),
    Column("trip_id", String, primary_key=True),
    Column("route_id", String, nullable=False),
    Column("line", String, nullable=False),
    Column("service_id", String, nullable=False),
    Column("direction_id", Integer),  # NULL until derived (design §4.3)
    Column("direction_source", String, nullable=False),
    Column("headsign", String),  # NULL until filled with the last stop name
    Column("shape_id", String, nullable=False),
    Index("ix_gtfs_trip_line_direction", "feed_version_id", "line", "direction_id"),
)

gtfs_stop_time = Table(
    "gtfs_stop_time",
    metadata,
    _fv(),
    Column("trip_id", String, primary_key=True),
    Column("stop_sequence", Integer, primary_key=True),
    Column("stop_id", String, nullable=False),
    Column("arrival_s", Integer, nullable=False),
    Column("departure_s", Integer, nullable=False),
    Column("shape_dist", Float),
    Index("ix_gtfs_stop_time_stop_arrival", "feed_version_id", "stop_id", "arrival_s"),
)

gtfs_shape_point = Table(
    "gtfs_shape_point",
    metadata,
    _fv(),
    Column("shape_id", String, primary_key=True),
    Column("sequence", Integer, primary_key=True),
    Column("lat", Float, nullable=False),
    Column("lon", Float, nullable=False),
    Column("dist", Float),
)

gtfs_calendar = Table(
    "gtfs_calendar",
    metadata,
    _fv(),
    Column("service_id", String, primary_key=True),
    *(Column(day, Boolean, nullable=False) for day in ("mon", "tue", "wed", "thu", "fri")),
    *(Column(day, Boolean, nullable=False) for day in ("sat", "sun")),
    Column("start_date", Date, nullable=False),
    Column("end_date", Date, nullable=False),
)

gtfs_calendar_date = Table(
    "gtfs_calendar_date",
    metadata,
    _fv(),
    Column("service_id", String, primary_key=True),
    Column("date", Date, primary_key=True),
    Column("exception_type", Integer, nullable=False),
)

line = Table(
    "line",
    metadata,
    _fv(),
    Column("short_name", String, primary_key=True),
    Column("long_name", String, nullable=False),
    Column("color", String, nullable=False),
    Column("text_color", String, nullable=False),
)

line_route = Table(
    "line_route",
    metadata,
    _fv(),
    Column("route_id", String, primary_key=True),
    Column("short_name", String, nullable=False),
)

line_direction = Table(
    "line_direction",
    metadata,
    _fv(),
    Column("short_name", String, primary_key=True),
    Column("direction_id", Integer, primary_key=True),
    Column("headsign", String, nullable=False),
    Column("shape_id", String, nullable=False),
    Column("trip_count", Integer, nullable=False),
)

stop_line_direction = Table(
    "stop_line_direction",
    metadata,
    _fv(),
    Column("stop_id", String, primary_key=True),
    Column("short_name", String, primary_key=True),
    Column("direction_id", Integer, primary_key=True),
)

line_direction_shape = Table(
    "line_direction_shape",
    metadata,
    _fv(),
    Column("short_name", String, primary_key=True),
    Column("direction_id", Integer, primary_key=True),
    Column("shape_id", String, primary_key=True),
    Column("trip_count", Integer, nullable=False),
)

stop_line_headsign = Table(
    "stop_line_headsign",
    metadata,
    _fv(),
    Column("stop_id", String, primary_key=True),
    Column("short_name", String, primary_key=True),
    Column("direction_id", Integer, primary_key=True),
    Column("headsign", String, primary_key=True),
    Column("trip_count", Integer, nullable=False),
)

VERSIONED_TABLES = tuple(table for name, table in metadata.tables.items() if name != "feed_version")
