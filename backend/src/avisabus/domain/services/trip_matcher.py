"""Pairing of real-time arrivals with scheduled trips (stop_arrivals_api design §3, ADR-013).

For the arrivals of the same line and direction, the assignment:

1. maximizes the number of matched arrivals;
2. with the same number, minimizes `Σ|scheduled_at − t|`;
3. uses each candidate at most once;
4. is strictly increasing in `scheduled_at` (later arrivals, later trips);
5. only pairs within `tolerance` (inclusive);

and breaks the remaining ties by the assignment's trip ids, compared in arrival order
(lexicographically; a matched arrival goes before an unmatched one). Duplicate arrival times are
distinct arrivals (AC-22). Real sizes are tiny (2–4 arrivals, a few candidates), so a memoized
alignment over (arrival, candidate) indexes is enough.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_UNMATCHED_KEY = (1, "")


@dataclass(frozen=True, slots=True)
class TripCandidate:
    trip_id: str
    service_date: date
    scheduled_at: datetime
    """Timezone-aware UTC."""


_Choice = tuple[int, timedelta, tuple[tuple[int, str], ...], tuple[int | None, ...]]
"""(−matched, total deviation, tie-break key, candidate index per arrival)."""


def match_trips(
    arrival_times: Sequence[datetime],
    candidates: Sequence[TripCandidate],
    tolerance: timedelta,
) -> list[TripCandidate | None]:
    """Trip of each arrival (same order as `arrival_times`), or `None` when unmatched."""
    order = sorted(range(len(arrival_times)), key=lambda index: arrival_times[index])
    times = [arrival_times[index] for index in order]
    trips = sorted(candidates, key=lambda c: (c.scheduled_at, c.trip_id))
    following = [
        next(
            (k for k in range(j + 1, len(trips)) if trips[k].scheduled_at > trip.scheduled_at),
            len(trips),
        )
        for j, trip in enumerate(trips)
    ]
    memo: dict[tuple[int, int], _Choice] = {}

    def best(i: int, j: int) -> _Choice:
        """Best assignment of arrivals `i…` using candidates from index `j` on."""
        if i == len(times):
            return 0, timedelta(), (), ()
        cached = memo.get((i, j))
        if cached is not None:
            return cached
        rest = best(i + 1, j)
        choice: _Choice = (rest[0], rest[1], (_UNMATCHED_KEY, *rest[2]), (None, *rest[3]))
        for k in range(j, len(trips)):
            deviation = abs(trips[k].scheduled_at - times[i])
            if deviation > tolerance:
                continue
            rest = best(i + 1, following[k])
            option: _Choice = (
                rest[0] - 1,
                rest[1] + deviation,
                ((0, trips[k].trip_id), *rest[2]),
                (k, *rest[3]),
            )
            if option[:3] < choice[:3]:
                choice = option
        memo[(i, j)] = choice
        return choice

    assigned = best(0, 0)[3]
    result: list[TripCandidate | None] = [None] * len(arrival_times)
    for position, index in enumerate(order):
        k = assigned[position]
        result[index] = None if k is None else trips[k]
    return result
