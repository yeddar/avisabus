"""App with the stop endpoints over `gtfs_mini` and a replayed SAE session (stop_arrivals_api)."""

import asyncio
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import Engine

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import StopUseCases, build_stop_use_cases
from avisabus.adapters.outbound.gtfs.reader import CsvGtfsFeedReader
from avisabus.adapters.outbound.occupancy.simulated_sensor import SimulatedOccupancySensor
from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_network import (
    SqliteGtfsFeedWriter,
    SqliteNetworkRepository,
)
from avisabus.adapters.outbound.persistence.sqlite_occupancy_override import (
    SqliteOccupancyOverrideRepository,
)
from avisabus.adapters.outbound.sae.cache import CachedArrivalsSource
from avisabus.adapters.outbound.sae.replay import SaeReplayArrivalsSource
from avisabus.adapters.outbound.security.hmac_stop_token import HmacStopTokenSigner
from avisabus.application.import_gtfs_feed import ImportGtfsFeed, ImportGtfsFeedCommand
from avisabus.config import Settings
from avisabus.domain.models.arrivals import ArrivalsSnapshot
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.occupancy import OccupancySensor

SECRET = "s" * 32
API = "/api/v1"


def stops_settings(**values: Any) -> Settings:
    return Settings(_env_file=None, env="test", stop_token_secret=SECRET, **values)  # type: ignore[call-arg]


def token(stop_id: str) -> str:
    return HmacStopTokenSigner(SECRET.encode()).sign(stop_id)


def new_engine(path: Path) -> Engine:
    engine = create_engine(stops_settings(database_url=f"sqlite:///{path}"))
    init_db(engine)
    return engine


def import_feed(engine: Engine, feed: Path) -> None:
    clock = _Fixed(datetime(2026, 10, 31, 8, 0, tzinfo=UTC))
    use_case = ImportGtfsFeed(CsvGtfsFeedReader, SqliteGtfsFeedWriter(engine), clock)
    asyncio.run(use_case.execute(ImportGtfsFeedCommand(feed)))


class _Fixed:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class CountingSource:
    """Counts the requests that reach the wrapped source (behind the cache)."""

    def __init__(self, inner: ArrivalsSource) -> None:
        self.inner = inner
        self.calls = 0

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        self.calls += 1
        return await self.inner.get_arrivals(stop_id)


def replay(
    session: Path, clock: Clock, start: datetime | None = None, ttl_s: float = 20
) -> tuple[CachedArrivalsSource, CountingSource]:
    """The replayed session behind the same cache as in production."""
    counting = CountingSource(SaeReplayArrivalsSource(session, clock, start))
    cached = CachedArrivalsSource(
        inner=counting,
        clock=clock,
        ttl=timedelta(seconds=ttl_s),
        error_ttl=timedelta(seconds=5),
        max_concurrency=4,
    )
    return cached, counting


def simulated_sensor(settings: Settings, engine: Engine, clock: Clock) -> SimulatedOccupancySensor:
    """Same construction as `avisabus.main.build_occupancy_sensor`."""
    return SimulatedOccupancySensor(
        network=SqliteNetworkRepository(engine),
        overrides=SqliteOccupancyOverrideRepository(engine),
        clock=clock,
        capacity=settings.occupancy_capacity,
        seats=settings.occupancy_seats,
        seed=settings.occupancy_seed,
        thresholds=settings.occupancy_thresholds(),
    )


@asynccontextmanager
async def stops_client(
    engine: Engine,
    clock: Clock,
    source: ArrivalsSource,
    settings: Settings | None = None,
    sensor: OccupancySensor | None = None,
    override_entries: Mapping[str, str] | None = None,
) -> AsyncIterator[tuple[httpx.AsyncClient, StopUseCases]]:
    settings = settings or stops_settings()
    use_cases = build_stop_use_cases(
        settings,
        engine,
        clock,
        source,
        sensor or simulated_sensor(settings, engine, clock),
        override_entries or {},
    )
    app = create_app(settings, stops=use_cases)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, use_cases
