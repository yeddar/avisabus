"""Occupancy reading, level classification and configuration checks (occupancy_sensor T-01)."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from avisabus.config import ConfigurationError, Settings
from avisabus.domain.models.occupancy import (
    OccupancyLevel,
    OccupancyReading,
    OccupancyStatus,
    OccupancyThresholds,
)
from avisabus.domain.services.occupancy_classifier import classify_occupancy

MEASURED_AT = datetime(2026, 11, 2, 8, 0, tzinfo=UTC)
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
