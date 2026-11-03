"""Fallback to the timetable when the SAE is unavailable (RF-09, stop_arrivals_api AC-13/AC-14)."""

from datetime import datetime, timedelta

from avisabus.domain.models.network import ScheduledStopTime
from avisabus.domain.ports.network import NetworkRepository


class ScheduledArrivalsProvider:
    def __init__(
        self,
        network: NetworkRepository,
        window: timedelta = timedelta(minutes=90),
        per_direction: int = 2,
    ) -> None:
        self._network = network
        self._window = window
        self._per_direction = per_direction

    def next_arrivals(self, stop_id: str, now: datetime) -> list[ScheduledStopTime]:
        """At most `per_direction` passages per (line, direction) in `[now, now + window]`, in
        time order (the order of `scheduled_stop_times`)."""
        taken: dict[tuple[str, int], int] = {}
        result = []
        for passage in self._network.scheduled_stop_times(stop_id, now, self._window):
            key = (passage.line, passage.direction_id)
            if taken.get(key, 0) < self._per_direction:
                taken[key] = taken.get(key, 0) + 1
                result.append(passage)
        return result
