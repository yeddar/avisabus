"""Use cases of the occupancy demo overrides with fakes (occupancy_sensor T-05)."""

from datetime import UTC, datetime, timedelta

import pytest

from avisabus.application.set_occupancy_override import (
    ClearOccupancyOverride,
    ClearOccupancyOverrideCommand,
    ListOccupancyOverrides,
    ListOccupancyOverridesQuery,
    SetOccupancyOverride,
    SetOccupancyOverrideCommand,
)
from avisabus.domain.errors import UnknownLineError
from avisabus.domain.models.network import Line
from avisabus.domain.models.occupancy import OccupancyLevel
from avisabus.domain.ports.occupancy import OccupancyOverride
from tests.support.fake_clock import FakeClock
from tests.support.occupancy import InMemoryOccupancyOverrideRepository

NOW = datetime(2026, 11, 2, 7, 30, tzinfo=UTC)
LINES = ("93", "70", "C2", "7")


class FakeLines:
    def get_line(self, short_name: str) -> Line | None:
        if short_name not in LINES:
            return None
        return Line(short_name, f"Line {short_name}", "000000", "FFFFFF", frozenset({short_name}))


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture
def overrides() -> InMemoryOccupancyOverrideRepository:
    return InMemoryOccupancyOverrideRepository()


def _set(overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock) -> SetOccupancyOverride:
    return SetOccupancyOverride(network=FakeLines(), overrides=overrides, clock=clock)  # type: ignore[arg-type]


@pytest.mark.spec("occupancy_sensor.AC-11")
async def test_set_stores_the_override_until_now_plus_minutes(
    overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> None:
    result = await _set(overrides, clock).execute(
        SetOccupancyOverrideCommand(line="93", level=OccupancyLevel.FULL, minutes=30)
    )
    expected = OccupancyOverride("93", OccupancyLevel.FULL, NOW + timedelta(minutes=30))
    assert result == expected
    assert overrides.active(NOW) == [expected]


@pytest.mark.spec("occupancy_sensor.AC-11")
async def test_set_lasts_thirty_minutes_by_default(
    overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> None:
    result = await _set(overrides, clock).execute(
        SetOccupancyOverrideCommand(line="93", level=OccupancyLevel.FREE)
    )
    assert result.expires_at == NOW + timedelta(minutes=30)


@pytest.mark.spec("occupancy_sensor.AC-11")
async def test_set_replaces_the_previous_override_of_the_line(
    overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> None:
    use_case = _set(overrides, clock)
    await use_case.execute(SetOccupancyOverrideCommand("93", OccupancyLevel.FULL, 30))
    await use_case.execute(SetOccupancyOverrideCommand("93", OccupancyLevel.MEDIUM, 10))
    assert overrides.active(NOW) == [
        OccupancyOverride("93", OccupancyLevel.MEDIUM, NOW + timedelta(minutes=10))
    ]


async def test_set_rejects_an_unknown_line(
    overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> None:
    with pytest.raises(UnknownLineError) as raised:
        await _set(overrides, clock).execute(
            SetOccupancyOverrideCommand("999", OccupancyLevel.FULL)
        )
    assert raised.value.line == "999"
    assert overrides.active(NOW) == []


@pytest.mark.parametrize("minutes", [0, -5])
async def test_set_rejects_a_non_positive_duration(
    overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock, minutes: int
) -> None:
    with pytest.raises(ValueError, match="minutes"):
        await _set(overrides, clock).execute(
            SetOccupancyOverrideCommand("93", OccupancyLevel.FULL, minutes)
        )
    assert overrides.active(NOW) == []


@pytest.mark.spec("occupancy_sensor.AC-12")
async def test_clear_removes_the_override_of_the_line(
    overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> None:
    await _set(overrides, clock).execute(SetOccupancyOverrideCommand("93", OccupancyLevel.FULL))
    await _set(overrides, clock).execute(SetOccupancyOverrideCommand("70", OccupancyLevel.FREE))
    clear = ClearOccupancyOverride(network=FakeLines(), overrides=overrides)  # type: ignore[arg-type]
    assert await clear.execute(ClearOccupancyOverrideCommand("93")) is True
    assert [o.line for o in overrides.active(NOW)] == ["70"]
    assert await clear.execute(ClearOccupancyOverrideCommand("93")) is False


@pytest.mark.spec("occupancy_sensor.AC-12")
async def test_clear_rejects_an_unknown_line(
    overrides: InMemoryOccupancyOverrideRepository,
) -> None:
    clear = ClearOccupancyOverride(network=FakeLines(), overrides=overrides)  # type: ignore[arg-type]
    with pytest.raises(UnknownLineError):
        await clear.execute(ClearOccupancyOverrideCommand("999"))


@pytest.mark.spec("occupancy_sensor.AC-13")
async def test_list_returns_active_overrides_in_natural_line_order(
    overrides: InMemoryOccupancyOverrideRepository, clock: FakeClock
) -> None:
    use_case = _set(overrides, clock)
    await use_case.execute(SetOccupancyOverrideCommand("C2", OccupancyLevel.FULL, 30))
    await use_case.execute(SetOccupancyOverrideCommand("93", OccupancyLevel.MEDIUM, 30))
    await use_case.execute(SetOccupancyOverrideCommand("70", OccupancyLevel.FREE, 5))
    await use_case.execute(SetOccupancyOverrideCommand("7", OccupancyLevel.FREE, 60))
    listing = ListOccupancyOverrides(overrides=overrides, clock=clock)
    result = await listing.execute(ListOccupancyOverridesQuery())
    assert [o.line for o in result] == ["7", "70", "93", "C2"]
    clock.advance(timedelta(minutes=5))
    result = await listing.execute(ListOccupancyOverridesQuery())
    assert [o.line for o in result] == ["7", "93", "C2"]
