"""Simulated `OccupancySensor` (RF-14, occupancy_sensor design §3).

Deterministic: the reading depends only on the trip, its service day, the instant asked for,
the configuration (capacity, seats, seed, thresholds) and, when there is one, the demo override
of the trip's line: the middle of the band of the forced level under the configured thresholds
(v1.1, `override_occupied`). Overrides are read through a 5 s cache so changes made from the
CLI (another process) are seen without restarting the application (AC-14).
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyThresholds,
    VehicleRef,
)
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.ports.occupancy import OccupancyOverride, OccupancyOverrideRepository
from avisabus.domain.services.occupancy_classifier import override_occupied
from avisabus.domain.services.occupancy_simulation import (
    hour_factor,
    progress,
    route_factor,
    simulate_occupied,
    trip_factor,
)

OVERRIDES_CACHE_TTL = timedelta(seconds=5)


@dataclass(frozen=True, slots=True)
class _CachedOverrides:
    fetched_at: datetime
    by_line: dict[str, OccupancyOverride]


class SimulatedOccupancySensor:
    def __init__(
        self,
        *,
        network: NetworkRepository,
        overrides: OccupancyOverrideRepository,
        clock: Clock,
        capacity: int,
        seats: int,
        seed: str,
        thresholds: OccupancyThresholds,
    ) -> None:
        self._network = network
        self._overrides = overrides
        self._clock = clock
        self._capacity = capacity
        self._seats = seats
        self._seed = seed
        self._override_occupied = _override_occupied_by_level(capacity, thresholds)
        self._cache: _CachedOverrides | None = None

    async def read(self, vehicle: VehicleRef, at: datetime) -> OccupancyReading | None:
        stop_times = self._network.trip_stop_times(vehicle.trip_id)
        if not stop_times:
            return None
        level = self._override_level(vehicle.trip_id)
        if level is not None:
            occupied = self._override_occupied[level]
        else:
            occupied = simulate_occupied(
                self._capacity,
                hour_factor(at),
                route_factor(progress(stop_times, vehicle.service_date, at)),
                trip_factor(self._seed, vehicle.trip_id, vehicle.service_date),
            )
        return OccupancyReading(
            capacity=self._capacity, seats=self._seats, occupied=occupied, measured_at=at
        )

    def _override_level(self, trip_id: str) -> OccupancyLevel | None:
        now = self._clock.now()
        overrides = self._active_overrides(now)
        if not overrides:
            return None
        line = self._network.trip_line(trip_id)
        override = None if line is None else overrides.get(line)
        if override is None or override.expires_at <= now:
            return None
        return override.level

    def _active_overrides(self, now: datetime) -> dict[str, OccupancyOverride]:
        cache = self._cache
        if cache is None or not timedelta(0) <= now - cache.fetched_at < OVERRIDES_CACHE_TTL:
            active = self._overrides.active(now)
            cache = _CachedOverrides(now, {override.line: override for override in active})
            self._cache = cache
        return cache.by_line


def _override_occupied_by_level(
    capacity: int, thresholds: OccupancyThresholds
) -> dict[OccupancyLevel, int]:
    """Occupied places of each forced level; `Settings` already rejects configurations where a
    level has none (occupancy_sensor AC-03), so a missing one here is a wiring error."""
    by_level: dict[OccupancyLevel, int] = {}
    for level in OccupancyLevel:
        occupied = override_occupied(level, capacity, thresholds)
        if occupied is None:
            raise ValueError(f"no whole number of occupied places is {level} for this capacity")
        by_level[level] = occupied
    return by_level
