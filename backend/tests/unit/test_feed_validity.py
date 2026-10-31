from datetime import UTC, date, datetime

import pytest

from avisabus.domain.models.network import CalendarException, FeedVersion, ServiceCalendar
from avisabus.domain.services.feed_validity import (
    Expired,
    Expiring,
    MissingValidityRangeError,
    Valid,
    feed_validity_range,
    feed_validity_status,
)
from tests.support.fake_clock import FakeClock

ALL_DAYS = (True,) * 7


def _feed(end: date) -> FeedVersion:
    return FeedVersion(
        version_id=1,
        feed_version="23-10-2026",
        imported_at=datetime(2026, 10, 23, 9, 0, tzinfo=UTC),
        start_date=date(2026, 10, 16),
        end_date=end,
        counts={},
    )


@pytest.mark.spec("gtfs_import.AC-19")
@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (datetime(2026, 10, 31, 8, 0, tzinfo=UTC), Valid()),
        (datetime(2026, 11, 14, 23, 0, tzinfo=UTC), Valid()),  # 8 days left
        (datetime(2026, 11, 15, 0, 0, tzinfo=UTC), Expiring(days_left=7)),
        (datetime(2026, 11, 17, 12, 0, tzinfo=UTC), Expiring(days_left=5)),
        (datetime(2026, 11, 22, 22, 0, tzinfo=UTC), Expiring(days_left=0)),  # last valid day
        (datetime(2026, 11, 23, 0, 0, tzinfo=UTC), Expired(days_ago=1)),
        (datetime(2026, 12, 2, 0, 0, tzinfo=UTC), Expired(days_ago=10)),
    ],
)
def test_status_depends_on_days_left_until_feed_end_date(
    now: datetime, expected: Valid | Expiring | Expired
) -> None:
    clock = FakeClock(now)
    status = feed_validity_status(_feed(date(2026, 11, 22)), clock.now().date())
    assert status == expected


@pytest.mark.spec("gtfs_import.AC-19")
def test_warning_threshold_is_configurable() -> None:
    feed = _feed(date(2026, 11, 22))
    assert feed_validity_status(feed, date(2026, 11, 12), warning_days=10) == Expiring(10)
    assert feed_validity_status(feed, date(2026, 11, 12), warning_days=7) == Valid()


@pytest.mark.spec("gtfs_import.AC-20")
def test_feed_info_dates_are_used_when_present() -> None:
    calendars = [ServiceCalendar("a", ALL_DAYS, date(2026, 10, 1), date(2026, 12, 31))]
    assert feed_validity_range(date(2026, 10, 16), date(2026, 11, 22), calendars, []) == (
        date(2026, 10, 16),
        date(2026, 11, 22),
    )


@pytest.mark.spec("gtfs_import.AC-20")
def test_without_feed_info_range_comes_from_calendar_and_calendar_dates() -> None:
    calendars = [
        ServiceCalendar("a", ALL_DAYS, date(2026, 10, 16), date(2026, 11, 22)),
        ServiceCalendar("b", ALL_DAYS, date(2026, 10, 20), date(2026, 11, 10)),
    ]
    exceptions = [
        CalendarException("x", date(2026, 10, 12), 1),
        CalendarException("a", date(2026, 11, 1), 2),
    ]
    assert feed_validity_range(None, None, calendars, exceptions) == (
        date(2026, 10, 12),
        date(2026, 11, 22),
    )
    late = [CalendarException("x", date(2026, 11, 30), 1)]
    assert feed_validity_range(None, None, calendars, late) == (
        date(2026, 10, 16),
        date(2026, 11, 30),
    )


@pytest.mark.spec("gtfs_import.AC-20")
def test_only_calendar_dates_without_feed_info() -> None:
    exceptions = [
        CalendarException("x", date(2026, 11, 5), 1),
        CalendarException("x", date(2026, 11, 2), 1),
    ]
    assert feed_validity_range(None, None, [], exceptions) == (
        date(2026, 11, 2),
        date(2026, 11, 5),
    )


@pytest.mark.spec("gtfs_import.AC-20")
def test_without_any_date_the_range_cannot_be_derived() -> None:
    with pytest.raises(MissingValidityRangeError):
        feed_validity_range(None, None, [], [])
