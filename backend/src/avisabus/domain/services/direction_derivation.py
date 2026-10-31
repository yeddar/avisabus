"""Derivation of `direction_id` for feeds whose `trips.txt` has no such column (design §4.3).

Pure: works per commercial line on its patterns (one per `shape_id`).
"""

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

Coordinate = tuple[float, float]
"""(lat, lon) in degrees."""

EARTH_RADIUS_M = 6_371_008.8
CIRCULAR_THRESHOLD_M = 500.0
NEGLIGIBLE_AREA_M2 = 1_000.0


@dataclass(frozen=True, slots=True)
class DirectionPattern:
    """A line pattern: a `shape_id` with the ends of one of its trips and its shape points."""

    shape_id: str
    first_stop: Coordinate
    last_stop: Coordinate
    shape_points: tuple[Coordinate, ...]
    trip_count: int


def haversine_m(a: Coordinate, b: Coordinate) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def signed_area_m2(points: Sequence[Coordinate]) -> float:
    """Shoelace area over an equirectangular projection: > 0 anticlockwise, < 0 clockwise."""
    if len(points) < 3:
        return 0.0
    lat0 = math.radians(sum(lat for lat, _ in points) / len(points))
    xy = [
        (
            math.radians(lon) * math.cos(lat0) * EARTH_RADIUS_M,
            math.radians(lat) * EARTH_RADIUS_M,
        )
        for lat, lon in points
    ]
    twice_area = 0.0
    for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1], strict=True):
        twice_area += x1 * y2 - x2 * y1
    return twice_area / 2


def _reference(patterns: Sequence[DirectionPattern]) -> DirectionPattern:
    """Most trips; ties broken by the lexicographically smaller `shape_id`."""
    return min(patterns, key=lambda p: (-p.trip_count, p.shape_id))


def derive_directions(
    patterns: Sequence[DirectionPattern],
    on_ambiguous: Callable[[str], None] | None = None,
) -> Mapping[str, int]:
    """Map each `shape_id` of one line to direction 0 or 1.

    Direction 0 is, by construction, the direction of the most frequent pattern. Patterns whose
    orientation cannot be determined (circular lines only) get 0 and are passed to
    `on_ambiguous`.
    """
    if not patterns:
        return {}
    ref = _reference(patterns)
    origin, destination = ref.first_stop, ref.last_stop
    if haversine_m(origin, destination) >= CIRCULAR_THRESHOLD_M:
        return {p.shape_id: _linear_direction(p, origin, destination) for p in patterns}
    return _circular_directions(patterns, ref, on_ambiguous)


def _linear_direction(pattern: DirectionPattern, origin: Coordinate, dest: Coordinate) -> int:
    same = haversine_m(pattern.first_stop, origin) + haversine_m(pattern.last_stop, dest)
    reverse = haversine_m(pattern.first_stop, dest) + haversine_m(pattern.last_stop, origin)
    return 0 if same <= reverse else 1


def _circular_directions(
    patterns: Sequence[DirectionPattern],
    ref: DirectionPattern,
    on_ambiguous: Callable[[str], None] | None,
) -> Mapping[str, int]:
    ref_area = signed_area_m2(ref.shape_points)
    result: dict[str, int] = {}
    for pattern in patterns:
        area = signed_area_m2(pattern.shape_points)
        if abs(area) < NEGLIGIBLE_AREA_M2 or abs(ref_area) < NEGLIGIBLE_AREA_M2:
            result[pattern.shape_id] = 0
            if on_ambiguous is not None:
                on_ambiguous(pattern.shape_id)
        else:
            result[pattern.shape_id] = 0 if (area > 0) == (ref_area > 0) else 1
    return result
