"""Synthetic patterns around València (lat ~39.47). 0.01 deg lat ~ 1.11 km, lon ~ 0.86 km."""

import pytest

from avisabus.domain.services.direction_derivation import (
    DirectionPattern,
    derive_directions,
    haversine_m,
    signed_area_m2,
)

A = (39.470, -0.400)  # west terminus
B = (39.470, -0.300)  # east terminus (~8.6 km from A)
C = (39.471, -0.320)  # short-turn stop near B


def _linear(shape_id: str, first: tuple[float, float], last: tuple[float, float], trips: int):
    return DirectionPattern(
        shape_id=shape_id,
        first_stop=first,
        last_stop=last,
        shape_points=(first, last),
        trip_count=trips,
    )


# Square loop of ~1.1 km x 0.86 km starting and ending at the south-west corner.
SW, NW, NE, SE = (39.470, -0.380), (39.480, -0.380), (39.480, -0.370), (39.470, -0.370)
CLOCKWISE = (SW, NW, NE, SE, SW)
ANTICLOCKWISE = (SW, SE, NE, NW, SW)
DEGENERATE = (SW, NW, SW)  # out and back along the same street: no area


def _loop(shape_id: str, points: tuple[tuple[float, float], ...], trips: int):
    return DirectionPattern(
        shape_id=shape_id,
        first_stop=points[0],
        last_stop=points[-1],
        shape_points=points,
        trip_count=trips,
    )


@pytest.mark.spec("gtfs_import.AC-24")
def test_linear_out_and_back_gets_two_directions_with_most_frequent_as_zero() -> None:
    patterns = [_linear("back", B, A, trips=8), _linear("out", A, B, trips=10)]
    assert derive_directions(patterns) == {"out": 0, "back": 1}


@pytest.mark.spec("gtfs_import.AC-24")
def test_short_variant_stays_in_the_direction_of_its_ends() -> None:
    patterns = [
        _linear("1055_487_2271", A, B, trips=74),
        _linear("1054_487_2229", A, C, trips=71),
        _linear("1055_2271_487", B, A, trips=72),
        _linear("1054_2229_487", C, A, trips=69),
    ]
    assert derive_directions(patterns) == {
        "1055_487_2271": 0,
        "1054_487_2229": 0,
        "1055_2271_487": 1,
        "1054_2229_487": 1,
    }


@pytest.mark.spec("gtfs_import.AC-24")
def test_trip_count_tie_is_broken_by_lexicographically_smaller_shape_id() -> None:
    patterns = [_linear("1070_2437_2285", B, A, 135), _linear("1070_2285_2437", A, B, 135)]
    assert derive_directions(patterns) == {"1070_2285_2437": 0, "1070_2437_2285": 1}


@pytest.mark.spec("gtfs_import.AC-24")
def test_tie_break_compares_strings_not_numbers() -> None:
    # "10_b" < "9_a" as strings although 10 > 9 as numbers.
    patterns = [_linear("9_a", A, B, 5), _linear("10_b", B, A, 5)]
    assert derive_directions(patterns) == {"10_b": 0, "9_a": 1}


@pytest.mark.spec("gtfs_import.AC-24")
def test_no_patterns_gives_no_directions() -> None:
    assert derive_directions([]) == {}


@pytest.mark.spec("gtfs_import.AC-25")
def test_circular_line_uses_shape_orientation() -> None:
    patterns = [
        _loop("cw_main", CLOCKWISE, trips=20),
        _loop("ccw", ANTICLOCKWISE, trips=15),
        _loop("cw_variant", CLOCKWISE[:-1] + ((39.4705, -0.3800),), trips=3),
    ]
    assert derive_directions(patterns) == {"cw_main": 0, "ccw": 1, "cw_variant": 0}


@pytest.mark.spec("gtfs_import.AC-25")
def test_circular_reference_orientation_defines_direction_zero() -> None:
    patterns = [_loop("ccw", ANTICLOCKWISE, trips=20), _loop("cw", CLOCKWISE, trips=15)]
    assert derive_directions(patterns) == {"ccw": 0, "cw": 1}


@pytest.mark.spec("gtfs_import.AC-25")
def test_degenerate_circular_shape_gets_zero_and_is_reported() -> None:
    reported: list[str] = []
    patterns = [
        _loop("cw", CLOCKWISE, trips=20),
        _loop("ccw", ANTICLOCKWISE, trips=15),
        _loop("flat", DEGENERATE, trips=2),
    ]
    result = derive_directions(patterns, on_ambiguous=reported.append)
    assert result == {"cw": 0, "ccw": 1, "flat": 0}
    assert reported == ["flat"]


@pytest.mark.spec("gtfs_import.AC-25")
def test_degenerate_reference_makes_every_orientation_undeterminable() -> None:
    reported: list[str] = []
    patterns = [_loop("flat", DEGENERATE, trips=20), _loop("ccw", ANTICLOCKWISE, trips=15)]
    assert derive_directions(patterns, on_ambiguous=reported.append) == {"flat": 0, "ccw": 0}
    assert sorted(reported) == ["ccw", "flat"]


@pytest.mark.spec("gtfs_import.AC-25")
def test_circular_threshold_is_500_metres_between_reference_ends() -> None:
    # Reference ends ~450 m apart -> circular (orientation decides, both loops clockwise -> 0).
    near_end = (39.474, -0.380)
    assert haversine_m(SW, near_end) < 500
    loop_a = (SW, NW, NE, SE, near_end)
    reverse_ends = DirectionPattern("b", near_end, SW, CLOCKWISE, trip_count=1)
    patterns = [DirectionPattern("a", SW, near_end, loop_a, trip_count=5), reverse_ends]
    assert derive_directions(patterns) == {"a": 0, "b": 0}
    # Reference ends ~560 m apart -> linear (ends decide, reversed ends -> 1).
    far_end = (39.475, -0.380)
    assert haversine_m(SW, far_end) >= 500
    reverse_far = DirectionPattern("b", far_end, SW, CLOCKWISE, trip_count=1)
    patterns = [DirectionPattern("a", SW, far_end, loop_a, trip_count=5), reverse_far]
    assert derive_directions(patterns) == {"a": 0, "b": 1}


def test_geometry_helpers() -> None:
    # ~1.11 km per 0.01 deg of latitude.
    assert haversine_m((39.47, -0.38), (39.48, -0.38)) == pytest.approx(1112, abs=2)
    assert signed_area_m2(CLOCKWISE) < 0 < signed_area_m2(ANTICLOCKWISE)
    assert abs(signed_area_m2(CLOCKWISE)) == pytest.approx(1112 * 858, rel=0.01)
    assert signed_area_m2(DEGENERATE) == pytest.approx(0, abs=1)
    assert signed_area_m2(()) == 0
