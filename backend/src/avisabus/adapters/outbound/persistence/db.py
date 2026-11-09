"""SQLite engine with the PRAGMAs of gtfs_import design §4.2. Schema via `create_all` (ADR-011)."""

from pathlib import Path
from typing import Any

import sqlalchemy
from sqlalchemy import Engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool

from avisabus.adapters.outbound.persistence.network_tables import metadata
from avisabus.adapters.outbound.persistence.sqlite_alerts import alert_metadata
from avisabus.adapters.outbound.persistence.sqlite_driver_codes import driver_code_metadata
from avisabus.adapters.outbound.persistence.sqlite_occupancy_override import occupancy_metadata
from avisabus.config import Settings

PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA synchronous=NORMAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
)


def create_engine(settings: Settings) -> Engine:
    url = make_url(settings.database_url)
    kwargs: dict[str, Any] = {}
    if url.database in (None, "", ":memory:"):
        # One shared connection so the in-memory database survives between uses.
        kwargs["poolclass"] = StaticPool
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    # hide_parameters: database errors must not carry bound values (hashes, labels) into traces.
    engine = sqlalchemy.create_engine(url, hide_parameters=True, **kwargs)
    event.listen(engine, "connect", _apply_pragmas)
    return engine


def _apply_pragmas(dbapi_connection: Any, _record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        for pragma in PRAGMAS:
            cursor.execute(pragma)
    finally:
        cursor.close()


def init_db(engine: Engine) -> None:
    """Create the network, `occupancy_override`, `alert` and `driver_code` tables (idempotent)."""
    metadata.create_all(engine)
    occupancy_metadata.create_all(engine)
    alert_metadata.create_all(engine)
    driver_code_metadata.create_all(engine)
