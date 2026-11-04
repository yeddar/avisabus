"""Composition root: builds the concrete adapters and wires them into the use cases.

Run with `uvicorn avisabus.main:app`. An invalid configuration (`ConfigurationError`) stops the
start-up here, before the database is opened.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
from fastapi import FastAPI
from sqlalchemy import Engine

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import (
    build_alert_snapshots,
    build_alert_use_cases,
    build_position_use_cases,
    build_realtime,
    build_stop_use_cases,
)
from avisabus.adapters.outbound.clock import SystemClock
from avisabus.adapters.outbound.occupancy.simulated_sensor import SimulatedOccupancySensor
from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.adapters.outbound.persistence.sqlite_occupancy_override import (
    SqliteOccupancyOverrideRepository,
)
from avisabus.adapters.outbound.sae.compose import build_arrivals_source
from avisabus.background.sae_stats import run_sae_stats
from avisabus.config import (
    Settings,
    log_dev_stop_token_secret_warning,
    read_direction_overrides,
)
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.occupancy import OccupancySensor
from avisabus.logging import configure_logging


def build_occupancy_sensor(settings: Settings, engine: Engine, clock: Clock) -> OccupancySensor:
    """Simulated sensor over the active network and the demo overrides (occupancy_sensor)."""
    return SimulatedOccupancySensor(
        network=SqliteNetworkRepository(engine),
        overrides=SqliteOccupancyOverrideRepository(engine),
        clock=clock,
        capacity=settings.occupancy_capacity,
        seats=settings.occupancy_seats,
        seed=settings.occupancy_seed,
        thresholds=settings.occupancy_thresholds(),
    )


settings = Settings()
configure_logging(settings.log_level)
log_dev_stop_token_secret_warning(settings)
clock = SystemClock()
http_client = httpx.AsyncClient()
arrivals_source = build_arrivals_source(
    settings, clock, http_client
)  # may raise ConfigurationError
direction_override_entries = read_direction_overrides(settings)  # may raise ConfigurationError
engine = create_engine(settings)
init_db(engine)
occupancy_sensor = build_occupancy_sensor(settings, engine, clock)
occupancy_thresholds = settings.occupancy_thresholds()
# Overrides are checked against the network active at start-up (stop_arrivals_api AC-20).
stop_use_cases = build_stop_use_cases(
    settings, engine, clock, arrivals_source, occupancy_sensor, direction_override_entries
)
# The position shares `GetStopArrivals` (and its SAE cache) with the stop endpoints.
position_use_cases = build_position_use_cases(stop_use_cases, engine, clock)
# Event publisher, device hasher and `/ws/passenger`, whose snapshot has the device's active
# alerts; the connection registry runs in the lifespan that `create_app` composes with this one
# (realtime_events, alert_create).
realtime = build_realtime(settings, clock, snapshots=build_alert_snapshots(engine))
# The alerts validate the bus with the stops' `GetStopArrivals` (same SAE cache) and publish their
# confirmation through the real-time publisher (alert_create).
alert_use_cases = build_alert_use_cases(settings, engine, clock, stop_use_cases, realtime.publisher)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Runs the `sae.stats` task (sae_arrivals_source AC-13) and closes the SAE HTTP client."""
    stats_task = asyncio.create_task(run_sae_stats(arrivals_source), name="sae.stats")
    try:
        yield
    finally:
        stats_task.cancel()
        with suppress(asyncio.CancelledError):
            await stats_task
        await http_client.aclose()


app = create_app(
    settings,
    lifespan=lifespan,
    stops=stop_use_cases,
    positions=position_use_cases,
    realtime=realtime,
    alerts=alert_use_cases,
)
