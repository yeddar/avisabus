"""Occupancy level of a reading (RF-15, occupancy_sensor design §2).

Also the number of occupied places that a demo override of a level stands for (design §3,
"Forzado", v1.1): the middle of the band of that level under the configured thresholds.
"""

from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyStatus,
    OccupancyThresholds,
)

_RANK = {OccupancyLevel.FREE: 0, OccupancyLevel.MEDIUM: 1, OccupancyLevel.FULL: 2}


def classify_occupancy(
    reading: OccupancyReading, thresholds: OccupancyThresholds
) -> OccupancyStatus:
    ratio = reading.occupied / reading.capacity
    free_seats = reading.free_seats
    return OccupancyStatus(
        level=_level(ratio, thresholds),
        has_free_seats=free_seats > 0,
        free_seats=free_seats,
        free_places=reading.free_places,
        ratio=ratio,
    )


def override_occupied(
    level: OccupancyLevel, capacity: int, thresholds: OccupancyThresholds
) -> int | None:
    """Occupied places that `level` is forced to, or None if no whole number is in its band.

    Starts at `round(capacity * r)`, with `r` the middle of the band of `level`
    (`medium / 2`, `(medium + full) / 2`, `(full + 1) / 2`), and, when rounding leaves the band,
    moves one place at a time towards it while staying within `0 … capacity`.
    """
    middle = {
        OccupancyLevel.FREE: thresholds.medium / 2,
        OccupancyLevel.MEDIUM: (thresholds.medium + thresholds.full) / 2,
        OccupancyLevel.FULL: (thresholds.full + 1) / 2,
    }[level]
    occupied = min(max(round(capacity * middle), 0), capacity)
    target = _RANK[level]
    rank = _RANK[_level(occupied / capacity, thresholds)]
    step = 1 if rank < target else -1
    # The walk stays within 0 … capacity: 0 places is always FREE (medium > 0) and `capacity`
    # places is always FULL (full <= 1), so it stops at the latest there.
    while rank != target:
        occupied += step
        rank = _RANK[_level(occupied / capacity, thresholds)]
        if (rank - target) * step > 0:  # jumped over the band: it has no whole number
            return None
    return occupied


def _level(ratio: float, thresholds: OccupancyThresholds) -> OccupancyLevel:
    if ratio < thresholds.medium:
        return OccupancyLevel.FREE
    if ratio < thresholds.full:
        return OccupancyLevel.MEDIUM
    return OccupancyLevel.FULL
