"""App with the stop, position and shape endpoints over `gtfs_mini` (position_estimation)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from sqlalchemy import Engine

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import (
    PositionUseCases,
    build_position_use_cases,
    build_stop_use_cases,
)
from avisabus.config import Settings
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock
from tests.support.stops import simulated_sensor, stops_settings


@asynccontextmanager
async def position_client(
    engine: Engine, clock: Clock, source: ArrivalsSource, settings: Settings | None = None
) -> AsyncIterator[tuple[httpx.AsyncClient, PositionUseCases]]:
    """Same composition as `avisabus.main`: the position shares the stops' `GetStopArrivals`."""
    settings = settings or stops_settings()
    stops = build_stop_use_cases(
        settings, engine, clock, source, simulated_sensor(settings, engine, clock), {}
    )
    positions = build_position_use_cases(stops, engine, clock)
    app = create_app(settings, stops=stops, positions=positions)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, positions
