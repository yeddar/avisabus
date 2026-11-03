"""Geometry on the shape of a trip (position_estimation design §3, T-01).

Synthetic shapes are built along a meridian (or a parallel) with known distances, so the expected
values do not depend on the functions under test.
"""

import math

import pytest

from avisabus.domain.models.network import ShapePoint
from avisabus.domain.services.geometry import (
    EARTH_RADIUS_M,
    bearing_deg,
    cumulative_distances,
    haversine_m,
    point_at_distance,
    project_onto_shape,
    shape_distances,
)

LAT0 = 39.45
LON0 = -0.38


def _north(d_m: float, lon: float = LON0) -> tuple[float, float]:
    """Point `d_m` metres north of (LAT0, lon) along its meridian (exact on the sphere)."""
    return LAT0 + math.degrees(d_m / EARTH_RADIUS_M), lon


def _east_offset_deg(d_m: float, lat: float) -> float:
    """Longitude difference for `d_m` metres east at latitude `lat` (small distances)."""
    return math.degrees(d_m / (EARTH_RADIUS_M * math.cos(math.radians(lat))))


def _shape(coords: list[tuple[float, float]], dists: list[float] | None = None) -> list[ShapePoint]:
    return [
        ShapePoint(lat, lon, n + 1, None if dists is None else dists[n])
        for n, (lat, lon) in enumerate(coords)
    ]


def _meridian_shape(stops_m: list[float], with_dist: bool = True) -> list[ShapePoint]:
    coords = [_north(d) for d in stops_m]
    return _shape(coords, stops_m if with_dist else None)


# --- haversine, bearing ---


def test_haversine_along_a_meridian_is_the_arc_length() -> None:
    a, b = _north(0), _north(1234.5)
    assert haversine_m(*a, *b) == pytest.approx(1234.5, abs=1e-6)
    assert haversine_m(*b, *a) == pytest.approx(1234.5, abs=1e-6)
    assert haversine_m(*a, *a) == 0


@pytest.mark.spec("position_estimation.AC-05")
@pytest.mark.parametrize(
    ("dlat", "dlon", "expected"),
    [(0.01, 0, 0.0), (0, 0.01, 90.0), (-0.01, 0, 180.0), (0, -0.01, 270.0)],
)
def test_bearing_of_the_cardinal_directions(dlat: float, dlon: float, expected: float) -> None:
    assert bearing_deg(LAT0, LON0, LAT0 + dlat, LON0 + dlon) == pytest.approx(expected, abs=0.01)


@pytest.mark.spec("position_estimation.AC-05")
def test_bearing_is_between_0_and_360() -> None:
    north_west = bearing_deg(LAT0, LON0, LAT0 + 0.01, LON0 - 0.01)
    assert 270 < north_west < 360
    south_east = bearing_deg(LAT0, LON0, LAT0 - 0.01, LON0 + 0.01)
    assert 90 < south_east < 180


# --- distances along the shape (AC-06) ---


@pytest.mark.spec("position_estimation.AC-06")
def test_cumulative_distances_add_up_haversine_from_the_first_point() -> None:
    shape = _meridian_shape([0, 250, 1000, 1000, 2600], with_dist=False)
    assert cumulative_distances(shape) == pytest.approx([0, 250, 1000, 1000, 2600], abs=1e-6)
    assert cumulative_distances([]) == []


@pytest.mark.spec("position_estimation.AC-06")
def test_shape_distances_use_the_feed_values_when_present() -> None:
    # The feed values are deliberately not the haversine distances: they must be kept.
    shape = _shape([_north(0), _north(1000), _north(2000)], [0, 1010.5, 2030])
    assert shape_distances(shape) == [0, 1010.5, 2030]


@pytest.mark.spec("position_estimation.AC-06")
def test_shape_distances_are_computed_when_the_feed_lacks_them() -> None:
    without = _shape([_north(0), _north(1000), _north(2000)])
    assert shape_distances(without) == pytest.approx([0, 1000, 2000], abs=1e-6)
    partial = [
        ShapePoint(lat, lon, n + 1, 0.0 if n == 0 else None)
        for n, (lat, lon) in enumerate([_north(0), _north(500)])
    ]
    assert shape_distances(partial) == pytest.approx([0, 500], abs=1e-6)


# --- point at a distance (AC-05) ---


@pytest.mark.spec("position_estimation.AC-05")
@pytest.mark.parametrize("d", [0.0, 1.0, 999.0, 1000.0, 1500.0, 2345.6, 4000.0])
def test_point_at_distance_on_a_straight_shape_is_within_one_metre(d: float) -> None:
    shape = _meridian_shape([0, 1000, 2000, 3000, 4000])
    point = point_at_distance(shape, shape_distances(shape), d)
    expected = _north(d)
    assert haversine_m(point.lat, point.lon, *expected) < 1
    assert point.bearing_deg == pytest.approx(0.0, abs=0.01)


@pytest.mark.spec("position_estimation.AC-05")
def test_point_at_distance_interpolates_between_the_points_that_contain_it() -> None:
    # North 1000 m, then east 1000 m: the point at 1500 m is 500 m east of the corner.
    corner = _north(1000)
    east = (corner[0], corner[1] + _east_offset_deg(1000, corner[0]))
    shape = _shape([_north(0), corner, east], [0, 1000, 2000])
    point = point_at_distance(shape, shape_distances(shape), 1500)
    expected = (corner[0], corner[1] + _east_offset_deg(500, corner[0]))
    assert haversine_m(point.lat, point.lon, *expected) < 1
    assert point.bearing_deg == pytest.approx(90.0, abs=0.05)
    before = point_at_distance(shape, shape_distances(shape), 400)
    assert before.bearing_deg == pytest.approx(0.0, abs=0.01)


@pytest.mark.spec("position_estimation.AC-05")
def test_point_at_distance_is_clamped_to_the_shape() -> None:
    shape = _meridian_shape([0, 1000, 2000])
    distances = shape_distances(shape)
    before = point_at_distance(shape, distances, -50)
    after = point_at_distance(shape, distances, 2500)
    assert (before.lat, before.lon) == pytest.approx(_north(0))
    assert (after.lat, after.lon) == pytest.approx(_north(2000))
    assert before.bearing_deg == pytest.approx(0.0, abs=0.01)
    assert after.bearing_deg == pytest.approx(0.0, abs=0.01)


@pytest.mark.spec("position_estimation.AC-05")
def test_bearing_skips_repeated_points() -> None:
    # Repeated points (zero-length segments) take the bearing of the closest real segment.
    shape = _shape([_north(0), _north(0), _north(1000), _north(1000)], [0, 0, 1000, 1000])
    distances = shape_distances(shape)
    assert point_at_distance(shape, distances, 0).bearing_deg == pytest.approx(0.0, abs=0.01)
    assert point_at_distance(shape, distances, 1000).bearing_deg == pytest.approx(0.0, abs=0.01)


def test_a_shape_of_one_point_has_no_bearing() -> None:
    shape = _shape([_north(0)], [0])
    point = point_at_distance(shape, [0.0], 10)
    assert (point.lat, point.lon, point.bearing_deg) == (*_north(0), None)
    with pytest.raises(ValueError, match="empty"):
        point_at_distance([], [], 0)


# --- projection of stops (AC-06) ---


@pytest.mark.spec("position_estimation.AC-06")
def test_stops_beside_the_shape_project_onto_their_distance() -> None:
    shape = _meridian_shape([0, 1000, 2000, 3000, 4000], with_dist=False)
    offset = _east_offset_deg(12, LAT0)  # stops on the pavement, 12 m from the shape
    stops = [(lat, lon + offset) for lat, lon in (_north(d) for d in (0, 950, 2000, 3999))]
    projected = project_onto_shape(stops, shape, shape_distances(shape))
    assert projected == pytest.approx([0, 950, 2000, 3999], abs=1)


@pytest.mark.spec("position_estimation.AC-06")
def test_projection_never_goes_back_along_the_trip() -> None:
    """Circular trip: out 2000 m north, 100 m east, back south 30 m east of the way out.

    The last stop has the coordinates of the first one, so its nearest point is the start of the
    shape; it must be projected on the way back, after the previous stops."""
    out_end = _north(2000)
    east = _east_offset_deg(30, LAT0)
    back_top = (out_end[0], out_end[1] + _east_offset_deg(30, out_end[0]))
    back_bottom = (LAT0, LON0 + east)
    shape = _shape([_north(0), out_end, back_top, back_bottom])
    distances = shape_distances(shape)
    stops = [_north(0), _north(1000), back_top, _north(0)]
    projected = project_onto_shape(stops, shape, distances)
    assert projected == sorted(projected)
    assert projected[0] == pytest.approx(0, abs=1)
    assert projected[1] == pytest.approx(1000, abs=1)
    assert projected[2] == pytest.approx(2030, abs=1)
    assert projected[3] == pytest.approx(distances[-1], abs=1)


@pytest.mark.spec("position_estimation.AC-06")
def test_projection_of_stops_out_of_order_does_not_decrease() -> None:
    shape = _meridian_shape([0, 1000, 2000], with_dist=False)
    # Second stop slightly behind the first one: kept at the first one's distance.
    stops = [_north(800), _north(790), _north(1500)]
    projected = project_onto_shape(stops, shape, shape_distances(shape))
    assert projected == sorted(projected)
    assert projected[0] == pytest.approx(800, abs=1)
    assert projected[1] == pytest.approx(projected[0])
    assert projected[2] == pytest.approx(1500, abs=1)


def test_projection_onto_a_shape_of_one_point() -> None:
    shape = _shape([_north(0)], [7.0])
    assert project_onto_shape([_north(10), _north(20)], shape, [7.0]) == [7.0, 7.0]
    assert project_onto_shape([], shape, [7.0]) == []
