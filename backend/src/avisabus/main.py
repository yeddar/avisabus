"""Composition root: builds the concrete adapters and wires them into the use cases.

Run with `uvicorn avisabus.main:app`. An invalid configuration (`ConfigurationError`) stops the
start-up here, before the database is opened.
"""

from sqlalchemy import Engine

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.outbound.clock import SystemClock
from avisabus.adapters.outbound.occupancy.simulated_sensor import SimulatedOccupancySensor
from avisabus.adapters.outbound.persistence.db import create_engine, init_db
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.adapters.outbound.persistence.sqlite_occupancy_override import (
    SqliteOccupancyOverrideRepository,
)
from avisabus.config import Settings
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
    )


settings = Settings()
configure_logging(settings.log_level)
clock = SystemClock()
engine = create_engine(settings)
init_db(engine)
occupancy_sensor = build_occupancy_sensor(settings, engine, clock)
occupancy_thresholds = settings.occupancy_thresholds()
app = create_app(settings)
