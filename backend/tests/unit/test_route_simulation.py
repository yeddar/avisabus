"""Positions of the route simulator over synthetic shapes (driver_gps_simulator T-01, AC-02).

The shapes run along a meridian, so the expected distances and points do not depend on the
functions under test.
"""

import math

import pytest

from avisabus.domain.models.network import ShapePoint
from avisabus.domain.services.geometry import EARTH_RADIUS_M, haversine_m
from avisabus.domain.services.route_simulation import SimulatedFix, simulate_route

LAT0 = 39.45
LON0 = -0.38
SPEED = 5.0  # m/s
INTERVAL = 4.0  # s → 20 m per step
STEP = SPEED * INTERVAL


def _north(d_m: float) -> tuple[float, float]:
    """Point `d_m` metres north of (LAT0, LON0) along its meridian (exact on the sphere)."""
    return LAT0 + math.degrees(d_m / EARTH_RADIUS_M), LON0


def _straight(length_m: float, every_m: float = 50.0) -> list[ShapePoint]:
    count = int(length_m // every_m)
    marks = [n * every_m for n in range(count + 1)]
    if marks[-1] < length_m:
        marks.append(length_m)
    return [ShapePoint(*_north(d), n + 1, None) for n, d in enumerate(marks)]


SHAPE = _straight(300.0)
STOPS = [("A", 10.0), ("B", 105.0), ("C", 250.0)]


def _run(
    stops: list[tuple[str, float]] = STOPS,
    dwell_s: float = 10.0,
    noise_m: float = 0.0,
    seed: int | None = None,
    shape: list[ShapePoint] = SHAPE,
) -> list[SimulatedFix]:
    return list(simulate_route(shape, stops, SPEED, INTERVAL, dwell_s, noise_m, seed))


def _lat_of(distance_m: float) -> float:
    return _north(distance_m)[0]


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_starts_at_the_first_stop_and_ends_with_one_fix_at_the_last() -> None:
    fixes = _run()
    assert fixes[0].elapsed_s == 0.0
    assert fixes[0].distance_m == pytest.approx(10.0)
    assert fixes[0].at_stop == "A"
    assert fixes[-1].distance_m == pytest.approx(250.0)
    assert fixes[-1].at_stop == "C"
    assert [fix.at_stop for fix in fixes].count("C") == 1


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_moves_speed_times_interval_per_send_and_stops_at_every_stop() -> None:
    # dwell 10 s every 4 s → ceil(10/4) = 3 extra fixes at each stop but the last one.
    fixes = _run(dwell_s=10.0)
    expected = (
        [(10.0, "A")] * 4
        + [(30.0, None), (50.0, None), (70.0, None), (90.0, None)]
        + [(105.0, "B")] * 4
        + [(125.0, None), (145.0, None), (165.0, None), (185.0, None), (205.0, None)]
        + [(225.0, None), (245.0, None), (250.0, "C")]
    )
    assert [(fix.distance_m, fix.at_stop) for fix in fixes] == [
        (pytest.approx(d), stop) for d, stop in expected
    ]
    assert [fix.elapsed_s for fix in fixes] == [n * INTERVAL for n in range(len(fixes))]


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_positions_lie_on_the_shape_at_their_distance() -> None:
    for fix in _run():
        assert fix.lat == pytest.approx(_lat_of(fix.distance_m), abs=1e-9)
        assert fix.lon == pytest.approx(LON0, abs=1e-12)


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_dwell_is_rounded_up_to_whole_intervals() -> None:
    def stays(dwell_s: float) -> int:
        return [fix.at_stop for fix in _run(dwell_s=dwell_s)].count("B")

    assert stays(0.0) == 1
    assert stays(4.0) == 2
    assert stays(4.1) == 3
    assert stays(12.0) == 4


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_a_step_that_would_cross_a_stop_ends_at_it() -> None:
    fixes = _run(stops=[("A", 0.0), ("B", 15.0), ("C", 40.0)], dwell_s=0.0)
    assert [(fix.distance_m, fix.at_stop) for fix in fixes] == [
        (pytest.approx(0.0), "A"),
        (pytest.approx(15.0), "B"),
        (pytest.approx(35.0), None),
        (pytest.approx(40.0), "C"),
    ]


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_a_trip_with_a_single_stop_is_a_single_fix() -> None:
    assert [(fix.distance_m, fix.at_stop) for fix in _run(stops=[("A", 30.0)])] == [
        (pytest.approx(30.0), "A")
    ]


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_noise_stays_within_the_radius_and_is_reproducible_with_the_seed() -> None:
    clean = _run()
    noisy = _run(noise_m=25.0, seed=7)
    again = _run(noise_m=25.0, seed=7)
    other = _run(noise_m=25.0, seed=8)

    assert noisy == again
    assert [(f.lat, f.lon) for f in noisy] != [(f.lat, f.lon) for f in other]
    offsets = [haversine_m(c.lat, c.lon, n.lat, n.lon) for c, n in zip(clean, noisy, strict=True)]
    assert max(offsets) <= 25.0 + 1e-6
    assert max(offsets) > 12.5  # the noise is really applied, not a tiny fraction of it
    assert [(f.elapsed_s, f.distance_m, f.at_stop) for f in noisy] == [
        (f.elapsed_s, f.distance_m, f.at_stop) for f in clean
    ]


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_noise_moves_points_in_every_direction() -> None:
    clean = _run(dwell_s=40.0)
    noisy = _run(dwell_s=40.0, noise_m=10.0, seed=1)
    north = [n.lat - c.lat for c, n in zip(clean, noisy, strict=True)]
    east = [n.lon - c.lon for c, n in zip(clean, noisy, strict=True)]
    assert min(north) < 0 < max(north)
    assert min(east) < 0 < max(east)


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_without_noise_the_seed_does_not_matter() -> None:
    assert _run(seed=1) == _run(seed=2) == _run()


@pytest.mark.spec("driver_gps_simulator.AC-02")
@pytest.mark.parametrize(
    ("shape", "stops", "speed", "interval", "dwell", "noise"),
    [
        ([], STOPS, SPEED, INTERVAL, 0.0, 0.0),
        (SHAPE, [], SPEED, INTERVAL, 0.0, 0.0),
        (SHAPE, [("A", 50.0), ("B", 40.0)], SPEED, INTERVAL, 0.0, 0.0),
        (SHAPE, STOPS, 0.0, INTERVAL, 0.0, 0.0),
        (SHAPE, STOPS, SPEED, 0.0, 0.0, 0.0),
        (SHAPE, STOPS, SPEED, INTERVAL, -1.0, 0.0),
        (SHAPE, STOPS, SPEED, INTERVAL, 0.0, -1.0),
        (SHAPE, STOPS, math.nan, INTERVAL, 0.0, 0.0),
        (SHAPE, STOPS, math.inf, INTERVAL, 0.0, 0.0),
    ],
)
def test_rejects_invalid_arguments(
    shape: list[ShapePoint],
    stops: list[tuple[str, float]],
    speed: float,
    interval: float,
    dwell: float,
    noise: float,
) -> None:
    with pytest.raises(ValueError, match="."):
        list(simulate_route(shape, stops, speed, interval, dwell, noise))
