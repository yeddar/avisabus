"""Occupancy reading, level classification and configuration checks (occupancy_sensor T-01)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from avisabus.config import ConfigurationError, Settings
from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyStatus,
    OccupancyThresholds,
)
from avisabus.domain.services.occupancy_classifier import classify_occupancy, override_occupied
from tests.support.occupancy import reachable_levels, threshold_configurations

MEASURED_AT = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
PROPERTIES = settings(max_examples=300, derandomize=True, database=None, deadline=None)
OCCUPANCY_VARIABLES = (
    "CAPACITY",
    "SEATS",
    "SEED",
    "THRESHOLD_MEDIUM",
    "THRESHOLD_FULL",
)


def _reading(occupied: int, capacity: int = 100, seats: int = 28) -> OccupancyReading:
    return OccupancyReading(
        capacity=capacity, seats=seats, occupied=occupied, measured_at=MEASURED_AT
    )


@pytest.mark.spec("occupancy_sensor.AC-01")
def test_reading_keeps_its_values_and_derives_free_places_and_free_seats() -> None:
    reading = OccupancyReading(capacity=90, seats=28, occupied=20, measured_at=MEASURED_AT)
    assert (reading.capacity, reading.seats, reading.occupied) == (90, 28, 20)
    assert reading.measured_at == MEASURED_AT
    assert reading.free_places == 70
    assert reading.free_seats == 8


@pytest.mark.spec("occupancy_sensor.AC-01")
@pytest.mark.parametrize(("occupied", "free_seats"), [(0, 28), (27, 1), (28, 0), (60, 0), (90, 0)])
def test_free_seats_never_goes_below_zero(occupied: int, free_seats: int) -> None:
    reading = OccupancyReading(capacity=90, seats=28, occupied=occupied, measured_at=MEASURED_AT)
    assert reading.free_seats == free_seats
    assert reading.free_places == 90 - occupied


@pytest.mark.spec("occupancy_sensor.AC-02")
@pytest.mark.parametrize(
    ("occupied", "level"),
    [
        (0, OccupancyLevel.FREE),
        (49, OccupancyLevel.FREE),
        (50, OccupancyLevel.MEDIUM),
        (84, OccupancyLevel.MEDIUM),
        (85, OccupancyLevel.FULL),
        (100, OccupancyLevel.FULL),
    ],
)
def test_classifies_by_ratio_with_default_thresholds(occupied: int, level: OccupancyLevel) -> None:
    status = classify_occupancy(_reading(occupied), OccupancyThresholds())
    assert status.level is level
    assert status.ratio == pytest.approx(occupied / 100)


@pytest.mark.spec("occupancy_sensor.AC-02")
def test_default_thresholds_are_half_and_eighty_five_percent() -> None:
    assert OccupancyThresholds() == OccupancyThresholds(medium=0.50, full=0.85)


@pytest.mark.spec("occupancy_sensor.AC-02")
@pytest.mark.parametrize(
    ("occupied", "level"),
    [
        (29, OccupancyLevel.FREE),
        (30, OccupancyLevel.MEDIUM),
        (69, OccupancyLevel.MEDIUM),
        (70, OccupancyLevel.FULL),
    ],
)
def test_thresholds_are_configurable(occupied: int, level: OccupancyLevel) -> None:
    status = classify_occupancy(_reading(occupied), OccupancyThresholds(medium=0.30, full=0.70))
    assert status.level is level


@pytest.mark.spec("occupancy_sensor.AC-02")
def test_status_reports_free_seats_and_free_places() -> None:
    status = classify_occupancy(_reading(20, capacity=90, seats=28), OccupancyThresholds())
    assert status == OccupancyStatus(
        level=OccupancyLevel.FREE,
        has_free_seats=True,
        free_seats=8,
        free_places=70,
        ratio=pytest.approx(20 / 90),
    )


@pytest.mark.spec("occupancy_sensor.AC-02")
@pytest.mark.parametrize("occupied", [28, 40])
def test_status_has_no_free_seats_when_every_seat_is_taken(occupied: int) -> None:
    status = classify_occupancy(_reading(occupied, capacity=90, seats=28), OccupancyThresholds())
    assert status.has_free_seats is False
    assert status.free_seats == 0


@pytest.fixture
def clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> pytest.MonkeyPatch:
    for name in OCCUPANCY_VARIABLES:
        monkeypatch.delenv(f"AVISABUS_OCCUPANCY_{name}", raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env file from the developer's checkout
    return monkeypatch


@pytest.mark.spec("occupancy_sensor.AC-03")
def test_occupancy_settings_have_documented_defaults(clean_environment: pytest.MonkeyPatch) -> None:
    settings = Settings()
    assert settings.occupancy_capacity == 90
    assert settings.occupancy_seats == 28
    assert settings.occupancy_seed == "avisabus"
    assert settings.occupancy_threshold_medium == 0.50
    assert settings.occupancy_threshold_full == 0.85


@pytest.mark.spec("occupancy_sensor.AC-03")
@pytest.mark.parametrize(
    ("medium", "full"),
    [("0.3", "0.7"), ("0.01", "1"), ("0.5", "0.85")],
)
def test_valid_thresholds_are_accepted(
    clean_environment: pytest.MonkeyPatch, medium: str, full: str
) -> None:
    clean_environment.setenv("AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM", medium)
    clean_environment.setenv("AVISABUS_OCCUPANCY_THRESHOLD_FULL", full)
    settings = Settings()
    assert settings.occupancy_threshold_medium == float(medium)
    assert settings.occupancy_threshold_full == float(full)


@pytest.mark.spec("occupancy_sensor.AC-03")
@pytest.mark.parametrize(
    ("medium", "full"),
    [
        ("0", "0.85"),  # medium must be > 0
        ("-0.1", "0.85"),
        ("0.85", "0.85"),  # medium must be < full
        ("0.9", "0.5"),
        ("0.5", "1.01"),  # full must be <= 1
    ],
)
def test_invalid_thresholds_refuse_to_start(
    clean_environment: pytest.MonkeyPatch, medium: str, full: str
) -> None:
    clean_environment.setenv("AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM", medium)
    clean_environment.setenv("AVISABUS_OCCUPANCY_THRESHOLD_FULL", full)
    with pytest.raises(ConfigurationError):
        Settings()


@pytest.mark.spec("occupancy_sensor.AC-03")
def test_more_seats_than_capacity_refuses_to_start(clean_environment: pytest.MonkeyPatch) -> None:
    clean_environment.setenv("AVISABUS_OCCUPANCY_CAPACITY", "40")
    clean_environment.setenv("AVISABUS_OCCUPANCY_SEATS", "41")
    with pytest.raises(ConfigurationError):
        Settings()


@pytest.mark.spec("occupancy_sensor.AC-03")
def test_as_many_seats_as_capacity_is_accepted(clean_environment: pytest.MonkeyPatch) -> None:
    clean_environment.setenv("AVISABUS_OCCUPANCY_CAPACITY", "40")
    clean_environment.setenv("AVISABUS_OCCUPANCY_SEATS", "40")
    assert Settings().occupancy_seats == 40


@pytest.mark.spec("occupancy_sensor.AC-03")
def test_settings_expose_the_configured_thresholds(clean_environment: pytest.MonkeyPatch) -> None:
    clean_environment.setenv("AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM", "0.4")
    clean_environment.setenv("AVISABUS_OCCUPANCY_THRESHOLD_FULL", "0.9")
    assert Settings().occupancy_thresholds() == OccupancyThresholds(medium=0.4, full=0.9)


# --- v1.1 (SP-01): every level must admit a whole number of occupied places ---


def _settings(capacity: int, medium: float, full: float) -> Settings:
    return Settings(  # type: ignore[call-arg]
        _env_file=None,
        env="test",
        occupancy_capacity=capacity,
        occupancy_seats=0,
        occupancy_threshold_medium=medium,
        occupancy_threshold_full=full,
    )


@pytest.mark.spec("occupancy_sensor.AC-03")
@pytest.mark.parametrize(
    ("capacity", "medium", "full"),
    [
        (3, 0.50, 0.60),  # MEDIUM needs 1.5 <= occupied < 1.8
        (1, 0.50, 0.85),  # default thresholds with a single place: no MEDIUM
        (10, 0.51, 0.59),  # MEDIUM needs 5.1 <= occupied < 5.9
    ],
)
def test_a_level_without_any_whole_number_of_places_refuses_to_start(
    capacity: int, medium: float, full: float
) -> None:
    with pytest.raises(ConfigurationError, match="MEDIUM"):
        _settings(capacity, medium, full)


@pytest.mark.spec("occupancy_sensor.AC-03")
@pytest.mark.parametrize(
    ("capacity", "medium", "full"),
    [(2, 0.50, 0.85), (3, 0.40, 0.70), (4, 0.25, 0.50), (90, 0.50, 0.85), (10, 0.50, 0.60)],
)
def test_small_capacities_where_every_level_fits_are_accepted(
    capacity: int, medium: float, full: float
) -> None:
    assert _settings(capacity, medium, full).occupancy_capacity == capacity


@pytest.mark.spec("occupancy_sensor.AC-03")
@PROPERTIES
@given(threshold_configurations())
def test_configuration_is_rejected_exactly_when_some_level_is_unreachable(
    configuration: tuple[int, OccupancyThresholds],
) -> None:
    capacity, thresholds = configuration
    every_level_fits = reachable_levels(capacity, thresholds) == set(OccupancyLevel)
    try:
        _settings(capacity, thresholds.medium, thresholds.full)
    except ConfigurationError:
        accepted = False
    else:
        accepted = True
    assert accepted is every_level_fits


# --- v1.1 (SP-01): occupied places of an override, from the configured thresholds ---


@pytest.mark.spec("occupancy_sensor.AC-11")
@pytest.mark.parametrize(
    ("level", "occupied"),
    [
        (OccupancyLevel.FREE, 22),  # round(90 * 0.25) = round(22.5)
        (OccupancyLevel.MEDIUM, 61),  # round(90 * 0.675) = round(60.75)
        (OccupancyLevel.FULL, 83),  # round(90 * 0.925) = round(83.25)
    ],
)
def test_override_takes_the_middle_of_the_band_of_the_default_thresholds(
    level: OccupancyLevel, occupied: int
) -> None:
    assert override_occupied(level, 90, OccupancyThresholds()) == occupied


@pytest.mark.spec("occupancy_sensor.AC-11")
@pytest.mark.parametrize(
    ("level", "occupied"),
    [
        (OccupancyLevel.FREE, 20),  # round(100 * 0.20)
        (OccupancyLevel.MEDIUM, 65),  # round(100 * 0.65)
        (OccupancyLevel.FULL, 95),  # round(100 * 0.95)
    ],
)
def test_override_follows_the_configured_thresholds(level: OccupancyLevel, occupied: int) -> None:
    assert override_occupied(level, 100, OccupancyThresholds(medium=0.40, full=0.90)) == occupied


@pytest.mark.spec("occupancy_sensor.AC-11")
def test_override_is_moved_into_the_band_when_rounding_leaves_it() -> None:
    # MEDIUM with capacity 4, thresholds 0.25 / 0.50: round(4 * 0.375) = round(1.5) = 2, and 2/4
    # is FULL; one place less (1/4) is MEDIUM.
    thresholds = OccupancyThresholds(medium=0.25, full=0.50)
    assert override_occupied(OccupancyLevel.MEDIUM, 4, thresholds) == 1


@pytest.mark.spec("occupancy_sensor.AC-11")
def test_override_is_none_when_the_band_has_no_whole_number() -> None:
    thresholds = OccupancyThresholds(medium=0.50, full=0.60)
    assert override_occupied(OccupancyLevel.MEDIUM, 3, thresholds) is None


@pytest.mark.spec("occupancy_sensor.AC-11")
@PROPERTIES
@given(threshold_configurations(), st.sampled_from(list(OccupancyLevel)))
def test_override_is_always_classified_as_the_requested_level_when_it_fits(
    configuration: tuple[int, OccupancyThresholds], level: OccupancyLevel
) -> None:
    capacity, thresholds = configuration
    occupied = override_occupied(level, capacity, thresholds)
    if level not in reachable_levels(capacity, thresholds):
        assert occupied is None
        return
    assert occupied is not None
    assert 0 <= occupied <= capacity
    reading = OccupancyReading(capacity, 0, occupied, MEASURED_AT)
    assert classify_occupancy(reading, thresholds).level is level
