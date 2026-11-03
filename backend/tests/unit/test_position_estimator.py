"""`estimate_position` on a synthetic trip (position_estimation design §3 and §5, T-02).

Straight trip along a meridian: five stops A–E every 1000 m and 120 s, from 08:00 local time of
Monday 2026-11-02. Distances along the shape are known, so the expected positions do not depend
on the code under test.
"""

import math
from datetime import date, datetime, timedelta

import pytest

from avisabus.domain.models.network import ShapePoint, TripStopTime
from avisabus.domain.models.position import PositionEstimate, PositionStatus, StopRef
from avisabus.domain.services.geometry import EARTH_RADIUS_M, haversine_m
from avisabus.domain.services.occupancy_simulation import service_day_start
from avisabus.domain.services.position_estimator import estimate_position

LAT0, LON0 = 39.45, -0.38
SERVICE_DATE = date(2026, 11, 2)
DAY_START = service_day_start(SERVICE_DATE)
DEPARTURE_S = 8 * 3600
STOPS = ("A", "B", "C", "D", "E")
NAMES = {stop: f"Stop {stop}" for stop in STOPS}


def _north(d_m: float) -> tuple[float, float]:
    return LAT0 + math.degrees(d_m / EARTH_RADIUS_M), LON0


def _shape(length_m: int = 4000, step_m: int = 250, with_dist: bool = True) -> list[ShapePoint]:
    points = []
    for n, d in enumerate(range(0, length_m + 1, step_m)):
        lat, lon = _north(d)
        points.append(ShapePoint(lat, lon, n + 1, float(d) if with_dist else None))
    return points


SHAPE = _shape()


def _trip(
    stops: tuple[str, ...] = STOPS, with_dist: bool = True, dwell_s: int = 0
) -> list[TripStopTime]:
    return [
        TripStopTime(
            stop,
            n + 1,
            DEPARTURE_S + 120 * n,
            DEPARTURE_S + 120 * n + dwell_s,
            1000.0 * n if with_dist else None,
        )
        for n, stop in enumerate(stops)
    ]


TRIP = _trip()


def _at(seconds: float) -> datetime:
    """Instant `seconds` after the trip's departure (08:00 local)."""
    return DAY_START + timedelta(seconds=DEPARTURE_S + seconds)


def _estimate(
    now_s: float,
    arrival_s: float,
    target: str = "E",
    trip: list[TripStopTime] = TRIP,
    shape: list[ShapePoint] = SHAPE,
    **kwargs: object,
) -> PositionEstimate:
    estimate = estimate_position(
        trip, shape, NAMES, target, DAY_START, _at(arrival_s), _at(now_s), **kwargs
    )
    assert estimate is not None
    return estimate


def _assert_at(estimate: PositionEstimate, d_m: float) -> None:
    assert estimate.shape_distance_m == pytest.approx(d_m, abs=1e-6)
    assert haversine_m(estimate.lat, estimate.lon, *_north(d_m)) < 1


# --- AC-01: between two stops, interpolated by time ---


@pytest.mark.spec("position_estimation.AC-01")
@pytest.mark.parametrize(
    ("now_s", "expected_d"),
    [(0, 0), (60, 500), (240, 2000), (300, 2500), (330, 2750), (479, 3991.6666666666665)],
)
def test_between_two_stops_the_bus_is_interpolated_by_time(now_s: float, expected_d: float) -> None:
    estimate = _estimate(now_s, arrival_s=480)  # on time at E
    assert estimate.status is PositionStatus.EN_ROUTE
    _assert_at(estimate, expected_d)
    assert estimate.bearing_deg == pytest.approx(0.0, abs=0.01)


@pytest.mark.spec("position_estimation.AC-01")
def test_two_stops_at_the_same_time_do_not_divide_by_zero() -> None:
    trip = list(TRIP)
    trip[2] = TripStopTime("C", 3, DEPARTURE_S + 120, DEPARTURE_S + 120, 2000.0)  # same as B
    for now_s, expected_d in ((60, 500), (120, 2000), (180, 2250)):
        estimate = _estimate(now_s, arrival_s=480, trip=trip)
        assert estimate.status is PositionStatus.EN_ROUTE
        _assert_at(estimate, expected_d)


@pytest.mark.spec("position_estimation.AC-01")
def test_uses_the_departure_of_the_previous_stop_and_the_arrival_of_the_next() -> None:
    trip = _trip(dwell_s=30)  # each stop: arrival at 120·n, departure 30 s later
    halfway = _estimate(240 + 30 + 45, arrival_s=480, trip=trip)  # C left at 270, D at 360
    _assert_at(halfway, 2500)
    dwelling = _estimate(240 + 10, arrival_s=480, trip=trip)  # still at C
    assert dwelling.status is PositionStatus.EN_ROUTE
    _assert_at(dwelling, 2000)


# --- AC-02: the delay is applied to the whole trip ---


@pytest.mark.spec("position_estimation.AC-02")
@pytest.mark.parametrize("now_s", [60, 200, 300, 470])
def test_a_bus_3_min_late_is_where_the_timetable_puts_it_3_min_earlier(now_s: float) -> None:
    late = _estimate(now_s + 180, arrival_s=480 + 180)
    on_time = _estimate(now_s, arrival_s=480)
    assert late == on_time
    assert late.status is PositionStatus.EN_ROUTE


@pytest.mark.spec("position_estimation.AC-02")
def test_an_early_bus_is_ahead_of_the_timetable() -> None:
    early = _estimate(300, arrival_s=480 - 60)
    _assert_at(early, 3000)


# --- AC-03: at the target stop ---


@pytest.mark.spec("position_estimation.AC-03")
@pytest.mark.parametrize(("now_s", "arrival_s"), [(480, 480), (500, 480), (700, 600), (300, 300)])
def test_at_or_after_the_scheduled_time_the_bus_is_at_the_stop(
    now_s: float, arrival_s: float
) -> None:
    estimate = _estimate(now_s, arrival_s)
    assert estimate.status is PositionStatus.AT_STOP
    _assert_at(estimate, 4000)
    assert estimate.distance_to_stop_m == 0
    assert estimate.stops_away == 0
    assert estimate.next_stop == StopRef("E", "Stop E")


@pytest.mark.spec("position_estimation.AC-03")
def test_an_arrival_of_0_minutes_is_at_the_stop() -> None:
    # "0 min": the arrival is now, whatever the timetable says.
    estimate = _estimate(100, arrival_s=100, target="D")
    assert estimate.status is PositionStatus.AT_STOP
    _assert_at(estimate, 3000)
    assert estimate.next_stop == StopRef("D", "Stop D")


# --- AC-04: before the trip starts ---


@pytest.mark.spec("position_estimation.AC-04")
@pytest.mark.parametrize(("now_s", "arrival_s"), [(-1, 480), (-600, 480), (100, 480 + 300)])
def test_before_the_departure_the_bus_is_at_the_first_stop(now_s: float, arrival_s: float) -> None:
    estimate = _estimate(now_s, arrival_s)
    assert estimate.status is PositionStatus.NOT_STARTED
    _assert_at(estimate, 0)
    assert estimate.distance_to_stop_m == pytest.approx(4000)
    assert estimate.bearing_deg == pytest.approx(0.0, abs=0.01)
    # Every stop after the first one and before E is still ahead.
    assert estimate.stops_away == 3
    assert estimate.next_stop == StopRef("B", "Stop B")


@pytest.mark.spec("position_estimation.AC-04")
def test_at_the_departure_the_bus_is_en_route() -> None:
    estimate = _estimate(0, arrival_s=480)
    assert estimate.status is PositionStatus.EN_ROUTE
    _assert_at(estimate, 0)


# --- AC-05: coordinates and bearing ---


@pytest.mark.spec("position_estimation.AC-05")
def test_coordinates_and_bearing_come_from_the_shape() -> None:
    # Southbound shape: the bus heads south (180°) and its position follows the shape.
    shape = [
        ShapePoint(lat, lon, n + 1, float(d))
        for n, (d, (lat, lon)) in enumerate((d, _north(4000 - d)) for d in range(0, 4001, 500))
    ]
    estimate = _estimate(300, arrival_s=480, shape=shape)
    assert haversine_m(estimate.lat, estimate.lon, *_north(1500)) < 1
    assert estimate.bearing_deg == pytest.approx(180.0, abs=0.01)


# --- AC-06: trips without shape_dist_traveled ---


@pytest.mark.spec("position_estimation.AC-06")
def test_without_distances_the_shape_and_the_stops_are_measured() -> None:
    coords = {stop: _north(1000 * n) for n, stop in enumerate(STOPS)}
    estimate = _estimate(
        300,
        arrival_s=480,
        trip=_trip(with_dist=False),
        shape=_shape(with_dist=False),
        stop_coordinates=coords,
    )
    assert estimate.status is PositionStatus.EN_ROUTE
    assert estimate.shape_distance_m == pytest.approx(2500, abs=1)
    assert haversine_m(estimate.lat, estimate.lon, *_north(2500)) < 1
    assert estimate.distance_to_stop_m == pytest.approx(1500, abs=1)
    assert estimate.next_stop == StopRef("D", "Stop D")


@pytest.mark.spec("position_estimation.AC-06")
def test_without_stop_distances_nor_coordinates_it_cannot_estimate() -> None:
    with pytest.raises(ValueError, match="coordinates"):
        _estimate(300, arrival_s=480, trip=_trip(with_dist=False))


# --- AC-07: circular lines ---


CIRCULAR = ("A", "B", "C", "D", "A")


@pytest.mark.spec("position_estimation.AC-07")
def test_a_repeated_target_uses_the_occurrence_closest_to_the_arrival() -> None:
    trip = _trip(CIRCULAR)  # A at 0 s and 0 m, and again at 480 s and 4000 m
    second = _estimate(300, arrival_s=470, target="A", trip=trip)
    assert second.status is PositionStatus.EN_ROUTE
    _assert_at(second, 2500 + 1000 * 10 / 120)  # δ = −10 s
    assert second.distance_to_stop_m == pytest.approx(4000 - second.shape_distance_m)
    assert second.stops_away == 1  # D
    first = _estimate(-60, arrival_s=10, target="A", trip=trip)
    assert first.status is PositionStatus.NOT_STARTED
    assert first.distance_to_stop_m == 0
    assert first.next_stop == StopRef("A", "Stop A")


@pytest.mark.spec("position_estimation.AC-07")
def test_the_closest_occurrence_is_chosen_by_the_arrival_not_by_now() -> None:
    trip = _trip(CIRCULAR)
    # Arrival in 2 min, 4 min late for the second A (480 s): the second A, not the first one.
    estimate = _estimate(480, arrival_s=600, target="A", trip=trip)
    _assert_at(estimate, 3000)  # shifted instant 360 s → at D
    assert estimate.next_stop == StopRef("A", "Stop A")


# --- AC-08: distance, stops away and next stop ---


@pytest.mark.spec("position_estimation.AC-08")
@pytest.mark.parametrize(
    ("target", "now_s", "distance", "stops_away", "next_stop"),
    [
        ("E", 300, 1500, 1, "D"),
        ("D", 300, 500, 0, "D"),
        ("E", 60, 3500, 3, "B"),
        ("E", 120, 3000, 2, "C"),  # exactly at B: B is behind
        ("C", 200, 333.3333333333333, 0, "C"),
    ],
)
def test_distance_stops_away_and_next_stop(
    target: str, now_s: float, distance: float, stops_away: int, next_stop: str
) -> None:
    arrival_s = 120 * STOPS.index(target)
    estimate = _estimate(now_s, arrival_s=arrival_s, target=target)
    assert estimate.status is PositionStatus.EN_ROUTE
    assert estimate.distance_to_stop_m == pytest.approx(distance)
    assert estimate.stops_away == stops_away
    assert estimate.next_stop == StopRef(next_stop, f"Stop {next_stop}")


def test_a_trip_without_the_target_stop_has_no_estimate() -> None:
    assert estimate_position(TRIP, SHAPE, NAMES, "Z", DAY_START, _at(480), _at(300)) is None


def test_stop_times_are_ordered_by_sequence() -> None:
    shuffled = [TRIP[3], TRIP[0], TRIP[4], TRIP[2], TRIP[1]]
    assert _estimate(300, 480, trip=shuffled) == _estimate(300, 480)
