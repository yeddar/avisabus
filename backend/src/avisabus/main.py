"""Composition root: builds the concrete adapters and wires them into the use cases.

Run with `uvicorn avisabus.main:app`. An invalid configuration (`ConfigurationError`) stops the
start-up here, before the database is opened.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

import httpx
import structlog
from fastapi import FastAPI
from sqlalchemy import Engine

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import (
    BACKGROUND_LOGGER,
    build_alert_expiry,
    build_alert_snapshots,
    build_alert_use_cases,
    build_driver_demand,
    build_driver_use_cases,
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
from avisabus.background.alert_tasks import start_alert_tasks, stop_tasks
from avisabus.background.driver_tasks import (
    VIEW_REFRESH_INTERVAL,
    start_demand_tasks,
    start_driver_tasks,
)
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
# Delivery of the requests and views of the drivers (driver_demand), wired into the alerts and
# the shifts below.
driver_demand = build_driver_demand(settings, engine, clock, occupancy_sensor, realtime)
# The alerts validate the bus with the stops' `GetStopArrivals` (same SAE cache) and publish their
# confirmation (alert_create) and cancellation (alert_cancel) through the real-time publisher.
alert_use_cases = build_alert_use_cases(
    settings, engine, clock, stop_use_cases, realtime.publisher, driver_demand
)
# Expiry of the alerts (alert_expiry): the passage watcher reads the stops through the same
# `GetStopArrivals` (and SAE cache); `alert.expired` goes through the real-time publisher.
alert_expiry = build_alert_expiry(
    settings, engine, clock, stop_use_cases, realtime.publisher, driver_demand
)
# Shifts of the drivers (driver_session), listened to by `driver_demand`.
driver_use_cases = build_driver_use_cases(settings, engine, clock, driver_demand.listener)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Runs the `sae.stats` task (sae_arrivals_source AC-13), the alert expiry tasks (alert_expiry
    AC-10), the driver session reaper (driver_session AC-13) and the refresh of the driver views
    (driver_demand AC-09), and closes the SAE HTTP client."""
    stats_task = asyncio.create_task(run_sae_stats(arrivals_source), name="sae.stats")
    expiry_tasks = start_alert_tasks(
        watch_tick=alert_expiry.watch_passages.tick,
        expiry_tick=alert_expiry.expire_due_alerts.tick,
        watch_interval=alert_expiry.watch_interval,
        expiry_interval=alert_expiry.expiry_interval,
        logger=structlog.get_logger(BACKGROUND_LOGGER),
    )
    driver_tasks = start_driver_tasks(
        reap_tick=driver_use_cases.reap.tick,
        interval=driver_use_cases.reaper_interval,
        logger=structlog.get_logger(BACKGROUND_LOGGER),
    )
    demand_tasks = start_demand_tasks(
        refresh_tick=driver_demand.views.refresh_all,
        interval=VIEW_REFRESH_INTERVAL,
        logger=structlog.get_logger(BACKGROUND_LOGGER),
    )
    try:
        yield
    finally:
        await stop_tasks([*expiry_tasks, *driver_tasks, *demand_tasks])
        await driver_demand.views.aclose()
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
    drivers=driver_use_cases,
    demand=driver_demand,
)
