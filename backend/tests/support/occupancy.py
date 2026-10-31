"""Fakes for the occupancy sensor tests (never used in production code)."""

from datetime import datetime

from avisabus.domain.models.network import TripStopTime
from avisabus.domain.ports.occupancy import OccupancyOverride


def stop_times(*arrivals: int) -> list[TripStopTime]:
    """Stop times of a trip with the given `arrival_s` values, one stop each."""
    return [
        TripStopTime(
            stop_id=f"S{n}",
            stop_sequence=n + 1,
            arrival_s=arrival,
            departure_s=arrival,
            shape_dist_traveled=None,
        )
        for n, arrival in enumerate(arrivals)
    ]


class FakeTripNetwork:
    """The part of `NetworkRepository` the occupancy sensor uses: trips and their lines."""

    def __init__(self) -> None:
        self._trips: dict[str, tuple[str, list[TripStopTime]]] = {}
        self.stop_time_queries: list[str] = []

    def add_trip(self, trip_id: str, line: str, times: list[TripStopTime]) -> None:
        self._trips[trip_id] = (line, times)

    def trip_stop_times(self, trip_id: str) -> list[TripStopTime]:
        self.stop_time_queries.append(trip_id)
        trip = self._trips.get(trip_id)
        return [] if trip is None else list(trip[1])

    def trip_line(self, trip_id: str) -> str | None:
        trip = self._trips.get(trip_id)
        return None if trip is None else trip[0]


class InMemoryOccupancyOverrideRepository:
    """`OccupancyOverrideRepository` in memory; counts the `active` queries."""

    def __init__(self) -> None:
        self._overrides: dict[str, OccupancyOverride] = {}
        self.active_queries = 0

    def set(self, override: OccupancyOverride) -> None:
        self._overrides[override.line] = override

    def clear(self, line: str) -> bool:
        return self._overrides.pop(line, None) is not None

    def active(self, now: datetime) -> list[OccupancyOverride]:
        self.active_queries += 1
        return sorted(
            (o for o in self._overrides.values() if o.expires_at > now), key=lambda o: o.line
        )
