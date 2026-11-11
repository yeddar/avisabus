"""Positions of a simulated bus along the shape of its trip (driver_gps_simulator design §2).

Pure and deterministic: the same arguments (and seed) always give the same positions (AC-02).
"""

import math
import random
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from avisabus.domain.models.network import ShapePoint
from avisabus.domain.services.geometry import (
    EARTH_RADIUS_M,
    cumulative_distances,
    point_at_distance,
)


@dataclass(frozen=True, slots=True)
class SimulatedFix:
    elapsed_s: float
    """Seconds since the first fix (one interval per fix)."""
    lat: float
    lon: float
    distance_m: float
    """Metres along the shape (real metres, as `cumulative_distances`), without the noise."""
    at_stop: str | None
    """`stop_id` of the stop the bus is stopped at, if any."""


def simulate_route(
    shape: Sequence[ShapePoint],
    stops: Sequence[tuple[str, float]],
    speed_mps: float,
    interval_s: float,
    dwell_s: float,
    noise_m: float = 0.0,
    seed: int | None = None,
) -> Iterator[SimulatedFix]:
    """Fixes every `interval_s` from the first stop to the last one (AC-02).

    `stops` are `(stop_id, metres along the shape)` in trip order. Each fix moves
    `speed_mps · interval_s` metres along the shape; a step that would reach or cross the next stop
    ends at it, and the bus then stays there `ceil(dwell_s / interval_s)` more fixes (also at the
    first stop). The last fix is the only one at the last stop. With `noise_m > 0` every point is
    moved uniformly within a disc of that radius, drawn with `random.Random(seed)`.

    Raises `ValueError` for an empty shape or trip, stops going backwards along the shape, or a
    speed, interval, dwell or noise out of range.
    """
    _check(shape, stops, speed_mps, interval_s, dwell_s, noise_m)
    return _fixes(shape, stops, speed_mps * interval_s, interval_s, dwell_s, noise_m, seed)


def _check(
    shape: Sequence[ShapePoint],
    stops: Sequence[tuple[str, float]],
    speed_mps: float,
    interval_s: float,
    dwell_s: float,
    noise_m: float,
) -> None:
    if not shape:
        raise ValueError("an empty shape has no points")
    if not stops:
        raise ValueError("a trip needs at least one stop")
    if any(later < earlier for (_, earlier), (_, later) in zip(stops, stops[1:], strict=False)):
        raise ValueError("the stops must not go backwards along the shape")
    if not (math.isfinite(speed_mps) and speed_mps > 0):
        raise ValueError("the speed must be positive")
    if not (math.isfinite(interval_s) and interval_s > 0):
        raise ValueError("the interval must be positive")
    if not (math.isfinite(dwell_s) and dwell_s >= 0):
        raise ValueError("the dwell time must not be negative")
    if not (math.isfinite(noise_m) and noise_m >= 0):
        raise ValueError("the noise must not be negative")


def _fixes(
    shape: Sequence[ShapePoint],
    stops: Sequence[tuple[str, float]],
    step_m: float,
    interval_s: float,
    dwell_s: float,
    noise_m: float,
    seed: int | None,
) -> Iterator[SimulatedFix]:
    distances = cumulative_distances(shape)
    rng = random.Random(seed)  # noqa: S311 - reproducible simulation, not security
    dwell_fixes = math.ceil(dwell_s / interval_s)
    last = len(stops) - 1
    sent = 0

    def fix(distance_m: float, at_stop: str | None) -> SimulatedFix:
        nonlocal sent
        point = point_at_distance(shape, distances, distance_m)
        lat, lon = _with_noise(point.lat, point.lon, noise_m, rng)
        elapsed_s = sent * interval_s
        sent += 1
        return SimulatedFix(elapsed_s, lat, lon, distance_m, at_stop)

    distance_m = stops[0][1]
    for index, (stop_id, stop_m) in enumerate(stops):
        while distance_m + step_m < stop_m:
            distance_m += step_m
            yield fix(distance_m, None)
        distance_m = stop_m
        yield fix(distance_m, stop_id)
        if index == last:
            return
        for _ in range(dwell_fixes):
            yield fix(distance_m, stop_id)


def _with_noise(lat: float, lon: float, noise_m: float, rng: random.Random) -> tuple[float, float]:
    """The point moved uniformly within a disc of radius `noise_m` (local plane, city scale)."""
    if noise_m <= 0:
        return lat, lon
    radius = noise_m * math.sqrt(rng.random())
    angle = 2 * math.pi * rng.random()
    north, east = radius * math.cos(angle), radius * math.sin(angle)
    return (
        lat + math.degrees(north / EARTH_RADIUS_M),
        lon + math.degrees(east / (EARTH_RADIUS_M * math.cos(math.radians(lat)))),
    )
