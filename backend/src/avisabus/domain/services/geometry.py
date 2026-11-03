"""Geometry on the shape of a trip (position_estimation design §3).

Distances are in metres on a sphere (haversine). Distances along a shape (`shape_dist_traveled`)
are taken from the feed when present (metres in EMT's feed) and computed otherwise (AC-06).
"""

import math
from bisect import bisect_right
from collections.abc import Sequence
from dataclasses import dataclass

from avisabus.domain.models.network import ShapePoint

EARTH_RADIUS_M = 6_371_008.8
"""Mean Earth radius (IUGG), in metres."""


@dataclass(frozen=True, slots=True)
class PointOnShape:
    lat: float
    lon: float
    bearing_deg: float | None
    """Bearing of the shape segment, in [0, 360); `None` if the shape has a single point."""


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance between two points, in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    h = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(h)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from the first point to the second one, in [0, 360) (0 = north)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_lambda = math.radians(lon2 - lon1)
    y = math.sin(d_lambda) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(d_lambda)
    return math.degrees(math.atan2(y, x)) % 360.0


def cumulative_distances(shape: Sequence[ShapePoint]) -> list[float]:
    """Distance travelled at every point of the shape (haversine), from 0 at the first one."""
    distances: list[float] = []
    total = 0.0
    for n, point in enumerate(shape):
        if n > 0:
            previous = shape[n - 1]
            total += haversine_m(previous.lat, previous.lon, point.lat, point.lon)
        distances.append(total)
    return distances


def shape_distances(shape: Sequence[ShapePoint]) -> list[float]:
    """`shape_dist_traveled` of the feed if every point has it, otherwise `cumulative_distances`
    (AC-06)."""
    feed = [point.dist_traveled for point in shape]
    if all(d is not None for d in feed):
        return [float(d) for d in feed if d is not None]
    return cumulative_distances(shape)


def point_at_distance(
    shape: Sequence[ShapePoint], distances: Sequence[float], d: float
) -> PointOnShape:
    """Point of the shape at distance `d` (clamped to the shape), interpolating linearly between
    the two points whose distances contain it, with the bearing of their segment (AC-05).

    Repeated points take the bearing of the next real segment (or the previous one at the end).
    """
    if not shape:
        raise ValueError("an empty shape has no points")
    if len(shape) == 1:
        return PointOnShape(shape[0].lat, shape[0].lon, None)
    last = len(shape) - 1
    if d <= distances[0]:
        segment, fraction = 0, 0.0
    elif d >= distances[last]:
        segment, fraction = last - 1, 1.0
    else:
        segment = min(bisect_right(distances, d) - 1, last - 1)
        length = distances[segment + 1] - distances[segment]
        fraction = 0.0 if length <= 0 else (d - distances[segment]) / length
    a, b = shape[segment], shape[segment + 1]
    lat = a.lat + fraction * (b.lat - a.lat)
    lon = a.lon + fraction * (b.lon - a.lon)
    return PointOnShape(lat, lon, _segment_bearing(shape, segment))


def _segment_bearing(shape: Sequence[ShapePoint], segment: int) -> float | None:
    candidates = [*range(segment, len(shape) - 1), *range(segment - 1, -1, -1)]
    for n in candidates:
        a, b = shape[n], shape[n + 1]
        if (a.lat, a.lon) != (b.lat, b.lon):
            return bearing_deg(a.lat, a.lon, b.lat, b.lon)
    return None


def project_onto_shape(
    points: Sequence[tuple[float, float]],
    shape: Sequence[ShapePoint],
    distances: Sequence[float],
) -> list[float]:
    """Distance along the shape of each point `(lat, lon)` (the stops of a trip, in order).

    Each point is projected onto a segment that is not before the previous point's one, choosing
    the segments that minimise the total distance from the points to the shape (dynamic
    programming over (point, segment)); the results never decrease (AC-06). Distances to the
    segments are measured on a local equirectangular plane, which is accurate at city scale.
    """
    if not points:
        return []
    if not shape:
        raise ValueError("an empty shape has no points")
    if len(shape) == 1:
        return [float(distances[0])] * len(points)
    ref_lat = math.radians(sum(p.lat for p in shape) / len(shape))
    ref_lon = shape[0].lon

    def plane(lat: float, lon: float) -> tuple[float, float]:
        x = EARTH_RADIUS_M * math.radians(lon - ref_lon) * math.cos(ref_lat)
        y = EARTH_RADIUS_M * math.radians(lat - shape[0].lat)
        return x, y

    vertices = [plane(p.lat, p.lon) for p in shape]
    segments = len(shape) - 1
    projections: list[list[tuple[float, float]]] = []  # (distance to the segment, fraction)
    for lat, lon in points:
        px, py = plane(lat, lon)
        projections.append(
            [_onto_segment(px, py, vertices[s], vertices[s + 1]) for s in range(segments)]
        )

    # cost[s]: best total distance of the points so far with the last one on segment `s`.
    cost = [projections[0][s][0] for s in range(segments)]
    back: list[list[int]] = []
    for row in projections[1:]:
        best_before: list[int] = []
        best = 0
        for s in range(segments):
            if cost[s] < cost[best]:
                best = s
            best_before.append(best)
        back.append(best_before)
        cost = [cost[best_before[s]] + row[s][0] for s in range(segments)]
    chosen = [min(range(segments), key=lambda s: (cost[s], s))]
    for best_before in reversed(back):
        chosen.append(best_before[chosen[-1]])
    chosen.reverse()

    result: list[float] = []
    for row, s in zip(projections, chosen, strict=True):
        fraction = row[s][1]
        d = distances[s] + fraction * (distances[s + 1] - distances[s])
        result.append(max(d, result[-1]) if result else d)
    return result


def _onto_segment(
    px: float, py: float, a: tuple[float, float], b: tuple[float, float]
) -> tuple[float, float]:
    """(distance from the point to segment `ab`, fraction of `ab` of its closest point)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    fraction = 0.0
    if length2 > 0:
        fraction = min(1.0, max(0.0, ((px - a[0]) * dx + (py - a[1]) * dy) / length2))
    cx, cy = a[0] + fraction * dx, a[1] + fraction * dy
    return math.hypot(px - cx, py - cy), fraction
