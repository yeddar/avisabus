"""`project_progress` and `upcoming_stops` on synthetic shapes (driver_session T-03)."""

import math

import pytest

from avisabus.domain.models.driver import UpcomingStop
from avisabus.domain.models.network import ShapePoint
from avisabus.domain.services.geometry import EARTH_RADIUS_M, cumulative_distances
from avisabus.domain.services.upcoming_stops import (
    AHEAD_MARGIN_M,
    FIRST_FIX_TOLERANCE_M,
    MAX_SPEED_MPS,
    OFF_ROUTE_M,
    PASSED_MARGIN_M,
    project_progress,
    upcoming_stops,
)

ORIGIN_LAT = 39.47
ORIGIN_LON = -0.37
TOLERANCE_M = 0.5


def _lat_lon(east_m: float, north_m: float) -> tuple[float, float]:
    lat = ORIGIN_LAT + math.degrees(north_m / EARTH_RADIUS_M)
    lon = ORIGIN_LON + math.degrees(east_m / (EARTH_RADIUS_M * math.cos(math.radians(ORIGIN_LAT))))
    return lat, lon


def _shape(*vertices: tuple[float, float]) -> list[ShapePoint]:
    points = []
    for n, (east, north) in enumerate(vertices, start=1):
        lat, lon = _lat_lon(east, north)
        points.append(ShapePoint(lat, lon, n, None))
    return points


STRAIGHT = _shape((0, 0), (1000, 0), (2000, 0), (5000, 0))
STRAIGHT_D = cumulative_distances(STRAIGHT)
# A square loop of 4 × 500 m that starts and ends at the same corner.
LOOP = _shape((0, 0), (500, 0), (500, 500), (0, 500), (0, 0))
LOOP_D = cumulative_distances(LOOP)
# Along a street for 1 km and back along the same street.
OUT_AND_BACK = _shape((0, 0), (1000, 0), (0, 0))
OUT_AND_BACK_D = cumulative_distances(OUT_AND_BACK)


def _project(
    shape: list[ShapePoint],
    distances: list[float],
    at: tuple[float, float],
    previous: float | None,
    elapsed: float | None = 5.0,
) -> tuple[float, float]:
    lat, lon = _lat_lon(*at)
    return project_progress(shape, distances, lat, lon, previous, elapsed)


def test_constants_of_the_design() -> None:
    assert PASSED_MARGIN_M == 20.0
    assert OFF_ROUTE_M == 150.0
    assert MAX_SPEED_MPS == 20.0
    assert AHEAD_MARGIN_M == 50.0
    assert FIRST_FIX_TOLERANCE_M == 30.0


@pytest.mark.spec("driver_session.AC-09")
def test_projects_onto_a_straight_shape() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (1500, 0), None)
    assert candidate == pytest.approx(1500, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_reports_the_distance_to_the_shape() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (1500, 80), None)
    assert candidate == pytest.approx(1500, abs=TOLERANCE_M)
    assert distance == pytest.approx(80, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_without_previous_progress_searches_the_whole_shape() -> None:
    candidate, _ = _project(STRAIGHT, STRAIGHT_D, (4800, 0), None)
    assert candidate == pytest.approx(4800, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_a_position_before_the_start_goes_to_the_start() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (-40, 0), None)
    assert candidate == pytest.approx(0, abs=TOLERANCE_M)
    assert distance == pytest.approx(40, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_a_position_past_the_end_goes_to_the_end() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (5040, 0), None)
    assert candidate == pytest.approx(5000, abs=TOLERANCE_M)
    assert distance == pytest.approx(40, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_search_does_not_go_further_back_than_100_m() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (500, 0), 1000)
    assert candidate == pytest.approx(900, abs=TOLERANCE_M)
    assert distance == pytest.approx(400, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_search_reaches_exactly_100_m_back() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (900, 0), 1000)
    assert candidate == pytest.approx(900, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_search_ahead_is_what_the_bus_could_have_travelled() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (2000, 0), 1000, elapsed=10)
    assert candidate == pytest.approx(1250, abs=TOLERANCE_M)
    assert distance == pytest.approx(750, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_search_reaches_exactly_the_travelled_distance() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (1250, 0), 1000, elapsed=10)
    assert candidate == pytest.approx(1250, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
@pytest.mark.parametrize("elapsed", [0.0, -30.0, None])
def test_without_elapsed_time_only_the_margin_is_ahead(elapsed: float | None) -> None:
    candidate, _ = _project(STRAIGHT, STRAIGHT_D, (2000, 0), 1000, elapsed=elapsed)
    assert candidate == pytest.approx(1050, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_a_gps_gap_of_five_minutes_widens_the_search() -> None:
    candidate, distance = _project(STRAIGHT, STRAIGHT_D, (4900, 0), 1000, elapsed=300)
    assert candidate == pytest.approx(4900, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_custom_back_distance() -> None:
    candidate, _ = _project(STRAIGHT, STRAIGHT_D, (500, 0), 1000)
    lat, lon = _lat_lon(500, 0)
    narrow, _ = project_progress(STRAIGHT, STRAIGHT_D, lat, lon, 1000, 5.0, back_m=10)
    assert candidate == pytest.approx(900, abs=TOLERANCE_M)
    assert narrow == pytest.approx(990, abs=TOLERANCE_M)


# The second pass over (300, 0) comes 400 m of route after the first one.
TWO_PASSES = _shape((0, 0), (400, 0), (400, -100), (300, -100), (300, 60), (300, 500))
TWO_PASSES_D = cumulative_distances(TWO_PASSES)


@pytest.mark.spec("driver_session.AC-09")
def test_a_later_pass_out_of_reach_is_ignored_even_if_closer() -> None:
    candidate, distance = _project(TWO_PASSES, TWO_PASSES_D, (300, 8), 290, elapsed=5)
    assert candidate == pytest.approx(300, abs=TOLERANCE_M)
    assert distance == pytest.approx(8, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_the_later_pass_is_found_when_it_is_within_reach() -> None:
    candidate, distance = _project(TWO_PASSES, TWO_PASSES_D, (300, 8), 290, elapsed=20)
    assert candidate == pytest.approx(708, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_the_first_position_takes_the_earliest_of_the_near_minimum_passes() -> None:
    candidate, distance = _project(TWO_PASSES, TWO_PASSES_D, (300, 29.5), None)
    assert candidate == pytest.approx(300, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_a_pass_farther_than_the_tolerance_is_not_taken_on_the_first_position() -> None:
    candidate, distance = _project(TWO_PASSES, TWO_PASSES_D, (300, 30.5), None)
    assert candidate == pytest.approx(730.5, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_the_first_position_reports_the_real_distance_to_the_shape() -> None:
    shape = _shape((0, 0), (1000, 0), (1000, 20), (0, 20))
    candidate, distance = _project(shape, cumulative_distances(shape), (500, 160), None)
    assert distance == pytest.approx(140, abs=TOLERANCE_M)
    assert candidate == pytest.approx(500, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_a_loop_is_at_its_start_without_previous_progress() -> None:
    candidate, _ = _project(LOOP, LOOP_D, (0, 0), None)
    assert candidate == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_a_loop_is_at_its_end_when_the_bus_comes_back() -> None:
    candidate, _ = _project(LOOP, LOOP_D, (0, 0), 1900)
    assert candidate == pytest.approx(2000, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_out_and_back_stays_on_the_outbound_leg() -> None:
    candidate, distance = _project(OUT_AND_BACK, OUT_AND_BACK_D, (300, 0), 200)
    assert candidate == pytest.approx(300, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_out_and_back_stays_on_the_return_leg() -> None:
    candidate, distance = _project(OUT_AND_BACK, OUT_AND_BACK_D, (800, 0), 1100)
    assert candidate == pytest.approx(1200, abs=TOLERANCE_M)
    assert distance == pytest.approx(0, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_out_and_back_starts_on_the_outbound_leg_without_previous_progress() -> None:
    candidate, _ = _project(OUT_AND_BACK, OUT_AND_BACK_D, (300, 0), None)
    assert candidate == pytest.approx(300, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_a_single_point_shape_is_that_point() -> None:
    shape = _shape((0, 0))
    candidate, distance = _project(shape, [0.0], (30, 40), None)
    assert candidate == 0.0
    assert distance == pytest.approx(50, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_an_empty_shape_is_an_error() -> None:
    with pytest.raises(ValueError, match="empty"):
        project_progress([], [], ORIGIN_LAT, ORIGIN_LON, None, None)


@pytest.mark.spec("driver_session.AC-09")
def test_a_window_past_the_shape_falls_back_to_its_end() -> None:
    candidate, _ = _project(STRAIGHT, STRAIGHT_D, (4000, 0), 9000)
    assert candidate == pytest.approx(5000, abs=TOLERANCE_M)


@pytest.mark.spec("driver_session.AC-09")
def test_repeated_points_are_harmless() -> None:
    shape = _shape((0, 0), (500, 0), (500, 0), (1000, 0))
    candidate, distance = _project(shape, cumulative_distances(shape), (500, 10), None)
    assert candidate == pytest.approx(500, abs=TOLERANCE_M)
    assert distance == pytest.approx(10, abs=TOLERANCE_M)


def _stops(*distances: float) -> list[tuple[UpcomingStop, float]]:
    return [
        (UpcomingStop(f"s{n}", f"Stop {n}", n, 0.0), distance)
        for n, distance in enumerate(distances, start=1)
    ]


@pytest.mark.spec("driver_session.AC-10")
def test_upcoming_are_the_stops_ahead_in_order() -> None:
    upcoming, finished = upcoming_stops(_stops(0, 400, 900, 1500), 500)
    assert [stop.stop_id for stop in upcoming] == ["s3", "s4"]
    assert finished is False


@pytest.mark.spec("driver_session.AC-10")
def test_upcoming_have_their_distance_ahead() -> None:
    upcoming, _ = upcoming_stops(_stops(0, 900, 1500), 500)
    assert [stop.distance_m for stop in upcoming] == [400, 1000]
    assert (upcoming[0].stop_id, upcoming[0].name, upcoming[0].stop_sequence) == (
        "s2",
        "Stop 2",
        2,
    )


@pytest.mark.spec("driver_session.AC-10")
def test_a_stop_exactly_20_m_ahead_is_not_upcoming() -> None:
    upcoming, _ = upcoming_stops(_stops(520, 2000), 500)
    assert [stop.stop_id for stop in upcoming] == ["s2"]


@pytest.mark.spec("driver_session.AC-10")
def test_a_stop_just_past_20_m_ahead_is_upcoming() -> None:
    upcoming, _ = upcoming_stops(_stops(520.5, 2000), 500)
    assert [stop.stop_id for stop in upcoming] == ["s1", "s2"]


@pytest.mark.spec("driver_session.AC-10")
def test_at_most_five_upcoming_stops_by_default() -> None:
    upcoming, _ = upcoming_stops(_stops(100, 200, 300, 400, 500, 600, 700), 0)
    assert [stop.stop_id for stop in upcoming] == ["s1", "s2", "s3", "s4", "s5"]


@pytest.mark.spec("driver_session.AC-10")
def test_limit_can_be_changed() -> None:
    upcoming, _ = upcoming_stops(_stops(100, 200, 300), 0, limit=2)
    assert [stop.stop_id for stop in upcoming] == ["s1", "s2"]


@pytest.mark.spec("driver_session.AC-10")
def test_finished_within_20_m_of_the_last_stop() -> None:
    upcoming, finished = upcoming_stops(_stops(100, 1000), 985)
    assert (upcoming, finished) == ((), True)


@pytest.mark.spec("driver_session.AC-10")
def test_finished_at_exactly_20_m_of_the_last_stop() -> None:
    assert upcoming_stops(_stops(100, 1000), 980) == ((), True)


@pytest.mark.spec("driver_session.AC-10")
def test_not_finished_just_before_20_m_of_the_last_stop() -> None:
    upcoming, finished = upcoming_stops(_stops(100, 1000), 979.5)
    assert finished is False
    assert [stop.stop_id for stop in upcoming] == ["s2"]


@pytest.mark.spec("driver_session.AC-10")
def test_finished_past_the_last_stop() -> None:
    assert upcoming_stops(_stops(100, 1000), 1500) == ((), True)


@pytest.mark.spec("driver_session.AC-10")
def test_without_stops_nothing_is_upcoming_nor_finished() -> None:
    assert upcoming_stops([], 100) == ((), False)
