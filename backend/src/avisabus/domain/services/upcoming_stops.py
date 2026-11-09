"""Progress of a bus along the shape of its trip and its next stops (driver_session design §3)."""

import math
from collections.abc import Sequence
from dataclasses import replace

from avisabus.domain.models.driver import UpcomingStop
from avisabus.domain.models.network import ShapePoint
from avisabus.domain.services.geometry import EARTH_RADIUS_M, haversine_m

PASSED_MARGIN_M = 20.0
OFF_ROUTE_M = 150.0
_TIE_DECIMALS = 3
"""Distances to the shape are equal when they match to the millimetre (same street twice)."""


def project_progress(
    shape: Sequence[ShapePoint],
    distances: Sequence[float],
    lat: float,
    lon: float,
    previous_m: float | None,
    back_m: float = 100.0,
    ahead_m: float = 3000.0,
) -> tuple[float, float]:
    """(candidate progress, distance to the shape) of the position on the closest stretch of the
    shape inside `[previous − back, previous + ahead]`, or anywhere if `previous_m` is `None`.

    The stretch is searched near the previous progress so that a shape passing twice through the
    same place (loops, out and back along a street) stays on the right pass; on a tie, the
    earliest one. Distances are measured on a local equirectangular plane, accurate at city
    scale.
    """
    if not shape:
        raise ValueError("an empty shape has no points")
    if len(shape) == 1:
        return float(distances[0]), haversine_m(shape[0].lat, shape[0].lon, lat, lon)
    low, high = _window(distances, previous_m, back_m, ahead_m)
    ref_lat = math.radians(sum(p.lat for p in shape) / len(shape))
    ref_lon = shape[0].lon
    origin_lat = shape[0].lat

    def plane(point_lat: float, point_lon: float) -> tuple[float, float]:
        x = EARTH_RADIUS_M * math.radians(point_lon - ref_lon) * math.cos(ref_lat)
        y = EARTH_RADIUS_M * math.radians(point_lat - origin_lat)
        return x, y

    px, py = plane(lat, lon)
    vertices = [plane(p.lat, p.lon) for p in shape]
    best: tuple[float, float] | None = None
    best_key: tuple[float, float] | None = None
    for s in range(len(shape) - 1):
        d_a, d_b = distances[s], distances[s + 1]
        if d_b < low or d_a > high:
            continue
        span = d_b - d_a
        f_low = 0.0 if span <= 0 else max(0.0, (low - d_a) / span)
        f_high = 1.0 if span <= 0 else min(1.0, (high - d_a) / span)
        distance, fraction = _closest_on_stretch(
            px, py, vertices[s], vertices[s + 1], f_low, f_high
        )
        candidate = d_a + fraction * span
        key = (round(distance, _TIE_DECIMALS), candidate)
        if best_key is None or key < best_key:
            best_key = key
            best = (candidate, distance)
    if best is None:  # unreachable: `_window` always overlaps some segment
        raise ValueError("no segment of the shape overlaps the window")
    return best


def _window(
    distances: Sequence[float], previous_m: float | None, back_m: float, ahead_m: float
) -> tuple[float, float]:
    """The search window, always overlapping the shape (the progress may be past its end if the
    network changed)."""
    if previous_m is None:
        return distances[0], distances[-1]
    low = min(previous_m - back_m, distances[-1])
    high = max(previous_m + ahead_m, distances[0])
    return low, high


def _closest_on_stretch(
    px: float,
    py: float,
    a: tuple[float, float],
    b: tuple[float, float],
    f_low: float,
    f_high: float,
) -> tuple[float, float]:
    """(distance from the point to the stretch `[f_low, f_high]` of `ab`, fraction of `ab` of the
    closest point)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    fraction = f_low
    if length2 > 0:
        projected = ((px - a[0]) * dx + (py - a[1]) * dy) / length2
        fraction = min(f_high, max(f_low, projected))
    return math.hypot(px - (a[0] + fraction * dx), py - (a[1] + fraction * dy)), fraction


def upcoming_stops(
    stops: Sequence[tuple[UpcomingStop, float]], progress_m: float, limit: int = 5
) -> tuple[tuple[UpcomingStop, ...], bool]:
    """(next stops, finished). `stops` are the stops of the trip, in order, each with its distance
    along the shape; the result carries the distance from the progress."""
    if not stops:
        return (), False
    if progress_m >= stops[-1][1] - PASSED_MARGIN_M:
        return (), True
    ahead = [
        replace(stop, distance_m=along - progress_m)
        for stop, along in stops
        if along > progress_m + PASSED_MARGIN_M
    ]
    return tuple(ahead[:limit]), False
