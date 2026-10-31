from datetime import UTC, datetime, timedelta, timezone

import pytest

from avisabus.adapters.outbound.clock import SystemClock
from avisabus.domain.ports.clock import Clock
from tests.support.fake_clock import FakeClock

START = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)


def _read(clock: Clock) -> datetime:
    return clock.now()


@pytest.mark.spec("project_scaffold.AC-07")
def test_system_clock_returns_timezone_aware_utc_datetimes() -> None:
    now = _read(SystemClock())
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


@pytest.mark.spec("project_scaffold.AC-07")
def test_fake_clock_returns_the_fixed_start_until_moved() -> None:
    clock = FakeClock(START)
    assert _read(clock) == START
    assert _read(clock) == START


@pytest.mark.spec("project_scaffold.AC-07")
def test_fake_clock_advances_by_the_given_delta() -> None:
    clock = FakeClock(START)
    clock.advance(timedelta(minutes=5, seconds=30))
    assert clock.now() == START + timedelta(minutes=5, seconds=30)


@pytest.mark.spec("project_scaffold.AC-07")
def test_fake_clock_can_be_set_to_an_arbitrary_instant() -> None:
    clock = FakeClock(START)
    target = datetime(2027, 1, 1, tzinfo=UTC)
    clock.set(target)
    assert clock.now() == target


@pytest.mark.spec("project_scaffold.AC-07")
def test_fake_clock_always_reports_utc() -> None:
    madrid_summer = timezone(timedelta(hours=2))
    clock = FakeClock(datetime(2026, 7, 1, 10, 0, tzinfo=madrid_summer))
    now = clock.now()
    assert now == datetime(2026, 7, 1, 8, 0, tzinfo=UTC)
    assert now.utcoffset() == timedelta(0)


@pytest.mark.spec("project_scaffold.AC-08")
def test_fake_clock_rejects_naive_start() -> None:
    with pytest.raises(ValueError):
        FakeClock(datetime(2026, 10, 31, 8, 0))


@pytest.mark.spec("project_scaffold.AC-08")
def test_fake_clock_rejects_naive_set() -> None:
    clock = FakeClock(START)
    with pytest.raises(ValueError):
        clock.set(datetime(2026, 10, 31, 9, 0))
    assert clock.now() == START
