from pathlib import Path

import pytest
from sqlalchemy import inspect, text

from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.network_tables import metadata
from avisabus.config import Settings

NETWORK_TABLES = {
    "feed_version",
    "gtfs_stop",
    "gtfs_route",
    "gtfs_trip",
    "gtfs_stop_time",
    "gtfs_shape_point",
    "gtfs_calendar",
    "gtfs_calendar_date",
    "line",
    "line_route",
    "line_direction",
    "stop_line_direction",
    "line_direction_shape",
    "stop_line_headsign",
}


def _settings(tmp_path: Path, name: str = "avisabus.sqlite") -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None, env="test", database_url=f"sqlite:///{tmp_path / 'sub' / name}"
    )


def test_db_engine_applies_pragmas(tmp_path: Path) -> None:
    engine = create_engine(_settings(tmp_path))
    with engine.connect() as conn:
        assert conn.execute(text("PRAGMA journal_mode")).scalar() == "wal"
        assert conn.execute(text("PRAGMA synchronous")).scalar() == 1  # NORMAL
        assert conn.execute(text("PRAGMA foreign_keys")).scalar() == 1
        assert conn.execute(text("PRAGMA busy_timeout")).scalar() == 5000
    engine.dispose()


def test_db_init_creates_every_network_table_and_is_idempotent(tmp_path: Path) -> None:
    engine = create_engine(_settings(tmp_path))
    init_db(engine)
    init_db(engine)
    tables = set(inspect(engine).get_table_names())
    assert tables >= NETWORK_TABLES
    assert set(metadata.tables) == NETWORK_TABLES
    engine.dispose()


def test_db_every_data_table_is_versioned(tmp_path: Path) -> None:
    for name, table in metadata.tables.items():
        if name == "feed_version":
            continue
        column = table.c.feed_version_id
        assert not column.nullable, name
        assert column.primary_key, name


def test_db_only_one_active_version_is_allowed(tmp_path: Path) -> None:
    engine = create_engine(_settings(tmp_path))
    init_db(engine)
    insert = text("INSERT INTO feed_version (is_active) VALUES (:active)")
    with engine.begin() as conn:
        conn.execute(insert, {"active": 1})
        conn.execute(insert, {"active": 0})
        conn.execute(insert, {"active": 0})
    with pytest.raises(Exception, match="UNIQUE"), engine.begin() as conn:
        conn.execute(insert, {"active": 1})
    engine.dispose()


def test_db_in_memory_url_is_supported() -> None:
    settings = Settings(_env_file=None, env="test", database_url="sqlite://")  # type: ignore[call-arg]
    engine = create_engine(settings)
    init_db(engine)
    assert "line" in inspect(engine).get_table_names()
    engine.dispose()
