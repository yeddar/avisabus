"""Pure functions of the simulated occupancy (occupancy_sensor design §3, T-02)."""

import math
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from avisabus.domain.models.network import TripStopTime
from avisabus.domain.models.occupancy import OccupancyReading, OccupancyThresholds
from avisabus.domain.services.occupancy_classifier import classify_occupancy
from avisabus.domain.services.occupancy_simulation import (
    hour_factor,
    progress,
    route_factor,
    simulate_occupied,
    trip_factor,
)

MADRID = ZoneInfo("Europe/Madrid")
MONDAY = date(2026, 11, 2)
SATURDAY = date(2026, 10, 31)
SUNDAY = date(2026, 11, 1)
SEED = "avisabus"
CAPACITY = 90
PEAK_HOURS = (7, 8, 17, 18, 19)
TRIPS = tuple(f"trip-{n}" for n in range(100))
PROPERTIES = settings(max_examples=300, derandomize=True, database=None, deadline=None)


def _local(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour, minute), tzinfo=MADRID)


def _occupied(trip_id: str, at: datetime, p: float, capacity: int = CAPACITY) -> int:
    return simulate_occupied(
        capacity,
        hour_factor(at),
        route_factor(p),
        trip_factor(SEED, trip_id, MONDAY),
    )


# --- hour_factor ---


@pytest.mark.parametrize(
    ("hour", "factor"),
    [
        (0, 0.15),
        (5, 0.15),
        (6, 0.40),
        (7, 1.00),
        (8, 1.00),
        (9, 0.60),
        (12, 0.60),
        (13, 0.85),
        (14, 0.85),
        (15, 0.60),
        (16, 0.60),
        (17, 0.95),
        (19, 0.95),
        (20, 0.45),
        (21, 0.45),
        (22, 0.25),
        (23, 0.25),
    ],
)
def test_hour_factor_follows_the_weekday_table(hour: int, factor: float) -> None:
    assert hour_factor(_local(MONDAY, hour, 30)) == pytest.approx(factor)
    assert hour_factor(_local(MONDAY, hour, 0)) == pytest.approx(factor)
    assert hour_factor(_local(MONDAY, hour, 59)) == pytest.approx(factor)


@pytest.mark.parametrize("day", [SATURDAY, SUNDAY])
@pytest.mark.parametrize(("hour", "weekday_factor"), [(3, 0.15), (8, 1.00), (18, 0.95)])
def test_hour_factor_is_reduced_on_weekends(day: date, hour: int, weekday_factor: float) -> None:
    assert hour_factor(_local(day, hour)) == pytest.approx(weekday_factor * 0.70)


def test_hour_factor_uses_madrid_local_time_for_utc_instants() -> None:
    # 2026-11-02 06:30 UTC is 07:30 in Madrid (CET): morning peak, not the 06-07 band.
    assert hour_factor(datetime(2026, 11, 2, 6, 30, tzinfo=UTC)) == pytest.approx(1.00)
    # 2026-10-31 22:30 UTC (Saturday) is already Sunday 2026-11-01 at 23:30 in Madrid.
    assert hour_factor(datetime(2026, 10, 31, 22, 30, tzinfo=UTC)) == pytest.approx(0.25 * 0.70)


# --- route_factor ---


@pytest.mark.parametrize(
    ("p", "factor"),
    [
        (0.0, 0.15),
        (1.0, 0.15),
        (0.5, 1.0),
        (0.25, math.sin(math.pi * 0.25) ** 0.8),
        (0.01, 0.15),
    ],
)
def test_route_factor_peaks_mid_route_with_a_floor(p: float, factor: float) -> None:
    assert route_factor(p) == pytest.approx(factor)


@PROPERTIES
@given(st.floats(min_value=0, max_value=1))
def test_route_factor_stays_between_floor_and_one(p: float) -> None:
    assert 0.15 <= route_factor(p) <= 1.0


# --- trip_factor ---


def test_trip_factor_is_deterministic_and_depends_on_seed_trip_and_day() -> None:
    base = trip_factor(SEED, "trip-1", MONDAY)
    assert trip_factor(SEED, "trip-1", MONDAY) == base
    assert trip_factor("other-seed", "trip-1", MONDAY) != base
    assert trip_factor(SEED, "trip-2", MONDAY) != base
    assert trip_factor(SEED, "trip-1", MONDAY + timedelta(days=1)) != base


@PROPERTIES
@given(st.text(), st.text(), st.dates())
def test_trip_factor_stays_in_its_range(seed: str, trip_id: str, service_date: date) -> None:
    assert 0.75 <= trip_factor(seed, trip_id, service_date) < 1.25


# --- simulate_occupied ---


def test_simulate_occupied_multiplies_the_factors_and_rounds() -> None:
    assert simulate_occupied(90, 0.6, 0.5, 1.0) == 27
    assert simulate_occupied(90, 1.0, 1.0, 0.75) == 68  # round(67.5) -> 68 (banker's: 68)


def test_simulate_occupied_caps_the_load_and_the_capacity() -> None:
    assert simulate_occupied(100, 1.0, 1.0, 1.2) == 100  # min(1.05, 1.2) * 100 -> capped
    assert simulate_occupied(100, 0.0, 1.0, 1.0) == 0


@pytest.mark.spec("occupancy_sensor.AC-05")
@PROPERTIES
@given(
    capacity=st.integers(min_value=1, max_value=500),
    h=st.floats(min_value=0, max_value=10, allow_nan=False),
    r=st.floats(min_value=0, max_value=10, allow_nan=False),
    t=st.floats(min_value=0, max_value=10, allow_nan=False),
)
def test_simulate_occupied_never_leaves_zero_to_capacity(
    capacity: int, h: float, r: float, t: float
) -> None:
    assert 0 <= simulate_occupied(capacity, h, r, t) <= capacity


@pytest.mark.spec("occupancy_sensor.AC-05")
@PROPERTIES
@given(
    capacity=st.integers(min_value=1, max_value=500),
    at=st.datetimes(
        min_value=datetime(2026, 1, 1),
        max_value=datetime(2027, 12, 31),
        timezones=st.just(UTC),
    ),
    p=st.floats(min_value=0, max_value=1),
    trip_id=st.text(min_size=1, max_size=20),
    service_date=st.dates(min_value=date(2026, 1, 1), max_value=date(2027, 12, 31)),
)
def test_simulated_occupancy_is_bounded_for_any_hour_day_and_progress(
    capacity: int, at: datetime, p: float, trip_id: str, service_date: date
) -> None:
    occupied = simulate_occupied(
        capacity, hour_factor(at), route_factor(p), trip_factor(SEED, trip_id, service_date)
    )
    assert 0 <= occupied <= capacity


@pytest.mark.spec("occupancy_sensor.AC-05")
@pytest.mark.parametrize("day", [MONDAY, SATURDAY, SUNDAY])
def test_simulated_occupancy_sweep_of_hours_and_progress_is_bounded(day: date) -> None:
    for hour in range(24):
        for step in range(11):
            for trip_id in TRIPS[:10]:
                occupied = _occupied(trip_id, _local(day, hour), step / 10)
                assert 0 <= occupied <= CAPACITY


# --- AC-06: rush hour vs 23:00 on a weekday ---


@pytest.mark.spec("occupancy_sensor.AC-06")
@pytest.mark.parametrize("hour", PEAK_HOURS)
@pytest.mark.parametrize("p", [0.0, 0.25, 0.5, 0.75, 1.0])
def test_rush_hour_occupancy_is_at_least_the_late_evening_one(hour: int, p: float) -> None:
    late = _local(MONDAY, 23)
    for minute in (0, 30, 59):
        for trip_id in TRIPS:
            peak = _occupied(trip_id, _local(MONDAY, hour, minute), p)
            assert peak >= _occupied(trip_id, late, p)


@pytest.mark.spec("occupancy_sensor.AC-06")
def test_rush_hour_is_strictly_busier_than_late_evening_mid_route() -> None:
    for trip_id in TRIPS:
        assert _occupied(trip_id, _local(MONDAY, 8), 0.5) > _occupied(
            trip_id, _local(MONDAY, 23), 0.5
        )


# --- AC-07: mid route vs ends ---


@pytest.mark.spec("occupancy_sensor.AC-07")
@pytest.mark.parametrize("hour", range(24))
def test_mid_route_is_busier_than_both_ends(hour: int) -> None:
    for day in (MONDAY, SUNDAY):
        at = _local(day, hour)
        for trip_id in TRIPS:
            middle = _occupied(trip_id, at, 0.5)
            assert middle > _occupied(trip_id, at, 0.0)
            assert middle > _occupied(trip_id, at, 1.0)


# --- AC-10: variation between trips ---


@pytest.mark.spec("occupancy_sensor.AC-10")
@pytest.mark.parametrize(("hour", "p"), [(8, 0.5), (10, 0.5), (18, 0.4)])
def test_one_hundred_trips_at_the_same_time_and_progress_give_several_levels(
    hour: int, p: float
) -> None:
    at = _local(MONDAY, hour)
    levels = {
        classify_occupancy(
            OccupancyReading(
                capacity=CAPACITY, seats=28, occupied=_occupied(trip_id, at, p), measured_at=at
            ),
            OccupancyThresholds(),
        ).level
        for trip_id in TRIPS
    }
    assert len(levels) >= 2


# --- progress (used by the sensor, AC-08) ---


def _stop_times(*arrivals: int) -> list[TripStopTime]:
    return [
        TripStopTime(
            stop_id=f"S{n}",
            stop_sequence=n + 1,
            arrival_s=s,
            departure_s=s,
            shape_dist_traveled=None,
        )
        for n, s in enumerate(arrivals)
    ]


EIGHT, NINE = 8 * 3600, 9 * 3600


@pytest.mark.spec("occupancy_sensor.AC-08")
@pytest.mark.parametrize(
    ("hour", "minute", "expected"),
    [(8, 0, 0.0), (8, 15, 0.25), (8, 30, 0.5), (9, 0, 1.0)],
)
def test_progress_is_the_elapsed_share_of_the_scheduled_trip(
    hour: int, minute: int, expected: float
) -> None:
    stop_times = _stop_times(EIGHT, EIGHT + 600, NINE)
    assert progress(stop_times, MONDAY, _local(MONDAY, hour, minute)) == pytest.approx(expected)


@pytest.mark.spec("occupancy_sensor.AC-08")
def test_progress_is_clamped_to_zero_and_one() -> None:
    stop_times = _stop_times(EIGHT, NINE)
    assert progress(stop_times, MONDAY, _local(MONDAY, 7, 0)) == 0.0
    assert progress(stop_times, MONDAY, _local(MONDAY, 10, 0)) == 1.0
    assert progress(stop_times, MONDAY, _local(MONDAY - timedelta(days=1), 8, 30)) == 0.0


@pytest.mark.spec("occupancy_sensor.AC-08")
def test_progress_counts_from_the_service_day_even_after_midnight() -> None:
    # Trip of the 2026-11-01 service day running from 23:30 to 24:30 (00:30 of 2026-11-02).
    stop_times = _stop_times(23 * 3600 + 1800, 24 * 3600 + 1800)
    at = _local(MONDAY, 0, 0)
    assert progress(stop_times, SUNDAY, at) == pytest.approx(0.5)


@pytest.mark.spec("occupancy_sensor.AC-08")
def test_progress_accepts_utc_instants() -> None:
    stop_times = _stop_times(EIGHT, NINE)
    # 07:30 UTC on 2026-11-02 is 08:30 in Madrid.
    assert progress(stop_times, MONDAY, datetime(2026, 11, 2, 7, 30, tzinfo=UTC)) == 0.5


@pytest.mark.spec("occupancy_sensor.AC-08")
def test_progress_uses_the_service_day_start_on_daylight_saving_days() -> None:
    # 2026-10-25 has 25 hours in Madrid. The GTFS service day starts at "noon minus 12 h"
    # (2026-10-24 23:00 UTC = 01:00 CEST), so GTFS 08:30 is 08:30 CET. Counting from local
    # midnight (22:00 UTC) would put 08:30 CET 9.5 h into the day and clamp the progress to 1.
    dst_day = date(2026, 10, 25)
    stop_times = _stop_times(EIGHT, NINE)
    assert progress(stop_times, dst_day, _local(dst_day, 8, 30)) == pytest.approx(0.5)


@pytest.mark.spec("occupancy_sensor.AC-08")
def test_progress_of_a_trip_with_a_single_instant() -> None:
    stop_times = _stop_times(EIGHT, EIGHT)
    assert progress(stop_times, MONDAY, _local(MONDAY, 7, 59)) == 0.0
    assert progress(stop_times, MONDAY, _local(MONDAY, 8, 0)) == 1.0


@pytest.mark.spec("occupancy_sensor.AC-08")
@PROPERTIES
@given(
    first=st.integers(min_value=0, max_value=30 * 3600),
    duration=st.integers(min_value=0, max_value=4 * 3600),
    offset=st.integers(min_value=-2 * 86400, max_value=2 * 86400),
)
def test_progress_is_always_between_zero_and_one(first: int, duration: int, offset: int) -> None:
    stop_times = _stop_times(first, first + duration)
    at = datetime(2026, 11, 2, tzinfo=MADRID) + timedelta(seconds=offset)
    assert 0.0 <= progress(stop_times, MONDAY, at) <= 1.0


def test_progress_of_a_trip_without_stop_times_is_an_error() -> None:
    with pytest.raises(ValueError, match="stop times"):
        progress([], MONDAY, _local(MONDAY, 8))
