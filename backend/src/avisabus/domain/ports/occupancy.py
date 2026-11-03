"""Occupancy ports (occupancy_sensor design §3).

`OccupancySensor` hides where the occupancy comes from (simulation today, real sensors
tomorrow, OBJ-08). `OccupancyOverrideRepository` stores the per-line demo overrides.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from avisabus.domain.models.occupancy import OccupancyLevel, OccupancyReading, VehicleRef


class OccupancySensor(Protocol):
    async def read(self, vehicle: VehicleRef, at: datetime) -> OccupancyReading | None:
        """Occupancy of the vehicle at `at`; `None` if the trip is not in the active network."""
        ...


@dataclass(frozen=True, slots=True)
class OccupancyOverride:
    """Demo override: every trip of `line` reads as `level` until `expires_at` (UTC)."""

    line: str
    level: OccupancyLevel
    expires_at: datetime


class OccupancyOverrideRepository(Protocol):
    def set(self, override: OccupancyOverride) -> None:
        """Create or replace the override of `override.line`."""
        ...

    def clear(self, line: str) -> bool:
        """Remove the override of `line`; `True` if there was one."""
        ...

    def active(self, now: datetime) -> list[OccupancyOverride]:
        """Overrides that have not expired at `now`."""
        ...
