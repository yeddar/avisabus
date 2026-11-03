"""Use cases of the per-line occupancy overrides for demos (occupancy_sensor design §2, §3).

While an override is active, the simulated sensor reports every trip of the line at the
forced level (AC-11). Overrides expire on their own or are cleared (AC-12).
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from avisabus.domain.errors import UnknownLineError
from avisabus.domain.models.network import Line
from avisabus.domain.models.occupancy import OccupancyLevel
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.occupancy import OccupancyOverride, OccupancyOverrideRepository
from avisabus.domain.services.line_order import natural_line_key

DEFAULT_OVERRIDE_MINUTES = 30


class LineCatalog(Protocol):
    """The part of `NetworkRepository` these use cases need."""

    def get_line(self, short_name: str) -> Line | None: ...


@dataclass(frozen=True, slots=True)
class SetOccupancyOverrideCommand:
    line: str
    level: OccupancyLevel
    minutes: int = DEFAULT_OVERRIDE_MINUTES


@dataclass(frozen=True, slots=True)
class ClearOccupancyOverrideCommand:
    line: str


@dataclass(frozen=True, slots=True)
class ListOccupancyOverridesQuery:
    pass


def _require_line(network: LineCatalog, line: str) -> None:
    if network.get_line(line) is None:
        raise UnknownLineError(line)


class SetOccupancyOverride:
    def __init__(
        self, network: LineCatalog, overrides: OccupancyOverrideRepository, clock: Clock
    ) -> None:
        self._network = network
        self._overrides = overrides
        self._clock = clock

    async def execute(self, command: SetOccupancyOverrideCommand) -> OccupancyOverride:
        """Create or replace the override of the line until now + `minutes`."""
        if command.minutes <= 0:
            raise ValueError("minutes must be positive")
        _require_line(self._network, command.line)
        override = OccupancyOverride(
            line=command.line,
            level=command.level,
            expires_at=self._clock.now() + timedelta(minutes=command.minutes),
        )
        self._overrides.set(override)
        return override


class ClearOccupancyOverride:
    def __init__(self, network: LineCatalog, overrides: OccupancyOverrideRepository) -> None:
        self._network = network
        self._overrides = overrides

    async def execute(self, command: ClearOccupancyOverrideCommand) -> bool:
        """`True` if the line had an override."""
        _require_line(self._network, command.line)
        return self._overrides.clear(command.line)


class ListOccupancyOverrides:
    def __init__(self, overrides: OccupancyOverrideRepository, clock: Clock) -> None:
        self._overrides = overrides
        self._clock = clock

    async def execute(self, query: ListOccupancyOverridesQuery) -> list[OccupancyOverride]:
        """Active overrides, lines in natural order."""
        active = self._overrides.active(self._clock.now())
        return sorted(active, key=lambda override: natural_line_key(override.line))
