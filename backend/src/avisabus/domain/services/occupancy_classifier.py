"""Occupancy level of a reading (RF-15, occupancy_sensor design §2)."""

from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyStatus,
    OccupancyThresholds,
)


def classify_occupancy(
    reading: OccupancyReading, thresholds: OccupancyThresholds
) -> OccupancyStatus:
    ratio = reading.occupied / reading.capacity
    if ratio < thresholds.medium:
        level = OccupancyLevel.FREE
    elif ratio < thresholds.full:
        level = OccupancyLevel.MEDIUM
    else:
        level = OccupancyLevel.FULL
    free_seats = reading.free_seats
    return OccupancyStatus(
        level=level,
        has_free_seats=free_seats > 0,
        free_seats=free_seats,
        free_places=reading.free_places,
        ratio=ratio,
    )
