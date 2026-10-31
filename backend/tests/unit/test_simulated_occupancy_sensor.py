"""`SimulatedOccupancySensor` with a fake network and in-memory overrides (T-04)."""

from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from avisabus.adapters.outbound.occupancy.simulated_sensor import SimulatedOccupancySensor
from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyThresholds,
    VehicleRef,
)
from avisabus.domain.ports.occupancy import OccupancyOverride, OccupancySensor
from avisabus.domain.services.occupancy_classifier import classify_occupancy
from avisabus.domain.services.occupancy_simulation import (
    hour_factor,
    route_factor,
    simulate_occupied,
    trip_factor,
)
from tests.support.fake_clock import FakeClock
from tests.support.occupancy import (
    FakeTripNetwork,
    InMemoryOccupancyOverrideRepository,
    stop_times,
)

MADRID = ZoneInfo("Europe/Madrid")
SERVICE_DATE = date(2026, 11, 2)  # Monday
NOW = datetime(2026, 11, 2, 7, 30, tzinfo=UTC)  # 08:30 in Madrid
CAPACITY, SEATS, SEED = 90, 28, "avisabus"
EIGHT, NINE = 8 * 3600, 9 * 3600
LINE_93_TRIPS = tuple(f"93-trip-{n}" for n in range(20))
LINE_70_TRIPS = tuple(f"70-trip-{n}" for n in range(20))


def _local(hour: int, minute: int = 0) -> datetime:
    return datetime.combine(SERVICE_DATE, time(hour, minute), tzinfo=MADRID)


@pytest.fixture
def network() -> FakeTripNetwork:
    network = FakeTripNetwork()
    for trip_id in LINE_93_TRIPS:
        network.add_trip(trip_id, "93", stop_times(EIGHT, EIGHT + 900, NINE))
    for trip_id in LINE_70_TRIPS:
        network.add_trip(trip_id, "70", stop_times(EIGHT, NINE))
    return network


@pytest.fixture
def overrides() -> InMemoryOccupancyOverrideRepository:
    return InMemoryOccupancyOverrideRepository()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


def _sensor(
    network: FakeTripNetwork,
    overrides: InMemoryOccupancyOverrideRepository,
    clock: FakeClock,
    seed: str = SEED,
) -> SimulatedOccupancySensor:
    return SimulatedOccupancySensor(
        network=network,  # type: ignore[arg-type]
        overrides=overrides,
        clock=clock,
        capacity=CAPACITY,
        seats=SEATS,
        seed=seed,
    )


@pytest.fixture
def sensor(
    network: FakeTripNetwork, overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> SimulatedOccupancySensor:
    return _sensor(network, overrides, clock)


def _vehicle(trip_id: str) -> VehicleRef:
    return VehicleRef(trip_id=trip_id, service_date=SERVICE_DATE)


async def _read(sensor: OccupancySensor, trip_id: str, at: datetime) -> OccupancyReading:
    reading = await sensor.read(_vehicle(trip_id), at)
    assert reading is not None
    return reading


def _level(reading: OccupancyReading) -> OccupancyLevel:
    return classify_occupancy(reading, OccupancyThresholds()).level


def _override(line: str, level: OccupancyLevel, minutes: int = 30) -> OccupancyOverride:
    return OccupancyOverride(line=line, level=level, expires_at=NOW + timedelta(minutes=minutes))


def test_sensor_satisfies_the_port(sensor: SimulatedOccupancySensor) -> None:
    port: OccupancySensor = sensor
    assert port is sensor


async def test_reading_has_the_configured_capacity_seats_and_instant(
    sensor: SimulatedOccupancySensor,
) -> None:
    at = _local(8, 30)
    reading = await _read(sensor, LINE_93_TRIPS[0], at)
    assert (reading.capacity, reading.seats, reading.measured_at) == (CAPACITY, SEATS, at)


# --- AC-04: determinism ---


@pytest.mark.spec("occupancy_sensor.AC-04")
async def test_same_trip_day_and_instant_always_give_the_same_reading(
    network: FakeTripNetwork, overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> None:
    at = _local(8, 40)
    first = _sensor(network, overrides, clock)
    second = _sensor(network, overrides, clock)  # e.g. after a restart
    for trip_id in LINE_93_TRIPS:
        reading = await _read(first, trip_id, at)
        assert await _read(first, trip_id, at) == reading
        assert await _read(second, trip_id, at) == reading


@pytest.mark.spec("occupancy_sensor.AC-04")
async def test_the_seed_is_configurable(
    network: FakeTripNetwork, overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> None:
    at = _local(8, 30)
    default = _sensor(network, overrides, clock)
    other = _sensor(network, overrides, clock, seed="other-seed")
    occupied = [(await _read(default, t, at)).occupied for t in LINE_93_TRIPS]
    other_occupied = [(await _read(other, t, at)).occupied for t in LINE_93_TRIPS]
    assert occupied != other_occupied
    for trip_id, value in zip(LINE_93_TRIPS, other_occupied, strict=True):
        expected = simulate_occupied(
            CAPACITY,
            hour_factor(at),
            route_factor(0.5),
            trip_factor("other-seed", trip_id, SERVICE_DATE),
        )
        assert value == expected


@pytest.mark.spec("occupancy_sensor.AC-04")
async def test_the_service_day_is_part_of_the_vehicle_identity(
    sensor: SimulatedOccupancySensor,
) -> None:
    # 08:30 of Monday and of Tuesday: same hour factor and progress, only the trip factor varies.
    at = _local(8, 30)
    next_day = SERVICE_DATE + timedelta(days=1)
    same = []
    for trip_id in LINE_93_TRIPS:
        today = await sensor.read(VehicleRef(trip_id, SERVICE_DATE), at)
        tomorrow = await sensor.read(VehicleRef(trip_id, next_day), at + timedelta(days=1))
        assert today is not None and tomorrow is not None
        assert tomorrow.occupied == simulate_occupied(
            CAPACITY,
            hour_factor(at),
            route_factor(0.5),
            trip_factor(SEED, trip_id, next_day),
        )
        same.append(today.occupied == tomorrow.occupied)
    assert not all(same)


# --- AC-08: progress from the scheduled stop times ---


@pytest.mark.spec("occupancy_sensor.AC-08")
@pytest.mark.parametrize(
    ("at", "p"),
    [
        (_local(7, 0), 0.0),  # before the first stop: clamped
        (_local(8, 0), 0.0),
        (_local(8, 15), 0.25),
        (_local(8, 30), 0.5),
        (_local(8, 45), 0.75),
        (_local(9, 0), 1.0),
        (_local(9, 50), 1.0),  # after the last stop: clamped
    ],
)
async def test_occupancy_follows_the_progress_computed_from_the_schedule(
    sensor: SimulatedOccupancySensor, network: FakeTripNetwork, at: datetime, p: float
) -> None:
    trip_id = LINE_93_TRIPS[3]
    reading = await _read(sensor, trip_id, at)
    expected = simulate_occupied(
        CAPACITY, hour_factor(at), route_factor(p), trip_factor(SEED, trip_id, SERVICE_DATE)
    )
    assert reading.occupied == expected
    assert network.stop_time_queries[-1] == trip_id


@pytest.mark.spec("occupancy_sensor.AC-08")
async def test_progress_uses_first_and_last_arrival_of_the_trip(
    sensor: SimulatedOccupancySensor, network: FakeTripNetwork
) -> None:
    # Same instant, different schedules: 08:30 is mid route of 08:00-09:00 but the start of
    # 08:30-10:30, so the first trip is busier.
    network.add_trip("mid", "93", stop_times(EIGHT, NINE))
    network.add_trip("start", "93", stop_times(EIGHT + 1800, NINE + 5400))
    at = _local(8, 30)
    mid = await _read(sensor, "mid", at)
    start = await _read(sensor, "start", at)
    assert mid.occupied == simulate_occupied(
        CAPACITY, hour_factor(at), route_factor(0.5), trip_factor(SEED, "mid", SERVICE_DATE)
    )
    assert start.occupied == simulate_occupied(
        CAPACITY, hour_factor(at), route_factor(0.0), trip_factor(SEED, "start", SERVICE_DATE)
    )


@pytest.mark.spec("occupancy_sensor.AC-08")
async def test_progress_of_a_trip_after_midnight_counts_from_its_service_day(
    sensor: SimulatedOccupancySensor, network: FakeTripNetwork
) -> None:
    network.add_trip("owl", "93", stop_times(23 * 3600 + 1800, 24 * 3600 + 1800))
    at = datetime(2026, 11, 3, 0, 0, tzinfo=MADRID)  # 24:00 of the 2026-11-02 service day
    reading = await _read(sensor, "owl", at)
    assert reading.occupied == simulate_occupied(
        CAPACITY, hour_factor(at), route_factor(0.5), trip_factor(SEED, "owl", SERVICE_DATE)
    )


# --- AC-09: unknown trip ---


@pytest.mark.spec("occupancy_sensor.AC-09")
async def test_unknown_trip_has_no_reading(sensor: SimulatedOccupancySensor) -> None:
    assert await sensor.read(_vehicle("ghost"), _local(8, 30)) is None


@pytest.mark.spec("occupancy_sensor.AC-09")
async def test_unknown_trip_has_no_reading_even_with_overrides(
    sensor: SimulatedOccupancySensor, overrides: InMemoryOccupancyOverrideRepository
) -> None:
    overrides.set(_override("93", OccupancyLevel.FULL))
    assert await sensor.read(_vehicle("ghost"), _local(8, 30)) is None


# --- AC-11: overrides ---


@pytest.mark.spec("occupancy_sensor.AC-11")
@pytest.mark.parametrize(
    ("level", "occupied"),
    [
        (OccupancyLevel.FREE, 18),  # round(90 * 0.20)
        (OccupancyLevel.MEDIUM, 58),  # round(90 * 0.65) = round(58.5)
        (OccupancyLevel.FULL, 86),  # round(90 * 0.95) = round(85.5)
    ],
)
async def test_override_forces_the_level_of_every_trip_of_the_line(
    sensor: SimulatedOccupancySensor,
    overrides: InMemoryOccupancyOverrideRepository,
    level: OccupancyLevel,
    occupied: int,
) -> None:
    overrides.set(_override("93", level))
    for hour in (3, 8, 23):
        at = _local(hour)
        for trip_id in LINE_93_TRIPS:
            reading = await _read(sensor, trip_id, at)
            assert reading.occupied == occupied
            assert _level(reading) is level
            assert reading.measured_at == at


@pytest.mark.spec("occupancy_sensor.AC-11")
async def test_override_does_not_change_other_lines(
    sensor: SimulatedOccupancySensor, overrides: InMemoryOccupancyOverrideRepository
) -> None:
    overrides.set(_override("93", OccupancyLevel.FULL))
    at = _local(8, 30)
    for trip_id in LINE_70_TRIPS:
        reading = await _read(sensor, trip_id, at)
        assert reading.occupied == simulate_occupied(
            CAPACITY, hour_factor(at), route_factor(0.5), trip_factor(SEED, trip_id, SERVICE_DATE)
        )


@pytest.mark.spec("occupancy_sensor.AC-11")
async def test_expired_override_no_longer_applies(
    sensor: SimulatedOccupancySensor,
    overrides: InMemoryOccupancyOverrideRepository,
    clock: FakeClock,
) -> None:
    overrides.set(_override("93", OccupancyLevel.FREE, minutes=1))
    at = _local(8, 30)
    trip_id = LINE_93_TRIPS[0]
    simulated = simulate_occupied(
        CAPACITY, hour_factor(at), route_factor(0.5), trip_factor(SEED, trip_id, SERVICE_DATE)
    )
    assert simulated != 18
    assert (await _read(sensor, trip_id, at)).occupied == 18
    clock.advance(timedelta(seconds=59))
    assert (await _read(sensor, trip_id, at)).occupied == 18
    clock.advance(timedelta(seconds=1))  # expires_at reached, even inside the cache window
    assert (await _read(sensor, trip_id, at)).occupied == simulated


# --- AC-14: overrides are read with a 5 s cache ---


@pytest.mark.spec("occupancy_sensor.AC-14")
async def test_override_changes_are_seen_within_five_seconds(
    sensor: SimulatedOccupancySensor,
    overrides: InMemoryOccupancyOverrideRepository,
    clock: FakeClock,
) -> None:
    trip_id = LINE_93_TRIPS[0]
    at = _local(8, 30)
    simulated = (await _read(sensor, trip_id, at)).occupied
    assert simulated != 86
    overrides.set(_override("93", OccupancyLevel.FULL))  # e.g. from the CLI, another process
    clock.advance(timedelta(seconds=4, milliseconds=999))
    assert (await _read(sensor, trip_id, at)).occupied == simulated  # still cached
    clock.advance(timedelta(milliseconds=1))
    assert (await _read(sensor, trip_id, at)).occupied == 86
    overrides.clear("93")
    clock.advance(timedelta(seconds=5))
    assert (await _read(sensor, trip_id, at)).occupied == simulated


@pytest.mark.spec("occupancy_sensor.AC-14")
async def test_overrides_are_queried_at_most_once_every_five_seconds(
    sensor: SimulatedOccupancySensor,
    overrides: InMemoryOccupancyOverrideRepository,
    clock: FakeClock,
) -> None:
    at = _local(8, 30)
    for trip_id in LINE_93_TRIPS:
        await _read(sensor, trip_id, at)
    assert overrides.active_queries == 1
    clock.advance(timedelta(seconds=4))
    await _read(sensor, LINE_93_TRIPS[0], at)
    assert overrides.active_queries == 1
    clock.advance(timedelta(seconds=1))
    await _read(sensor, LINE_93_TRIPS[0], at)
    assert overrides.active_queries == 2
