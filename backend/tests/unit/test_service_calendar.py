from datetime import date

import pytest

from avisabus.domain.models.network import CalendarException, ServiceCalendar
from avisabus.domain.services.service_calendar import active_services

WEEKDAYS = (True, True, True, True, False, False, False)  # Monday-Thursday
FRIDAY = (False, False, False, False, True, False, False)

CALENDARS = [
    ServiceCalendar("weekday", WEEKDAYS, date(2026, 10, 16), date(2026, 11, 22)),
    ServiceCalendar("friday", FRIDAY, date(2026, 10, 16), date(2026, 11, 22)),
    ServiceCalendar("short", WEEKDAYS, date(2026, 11, 2), date(2026, 11, 3)),
]
EXCEPTIONS = [
    # Holiday on Monday 2026-11-02: weekday service removed, a special one added.
    CalendarException("weekday", date(2026, 11, 2), 2),
    CalendarException("holiday_EXC", date(2026, 11, 2), 1),
    # Service that only exists in calendar_dates.
    CalendarException("only_dates", date(2026, 11, 7), 1),
    # Adding a service that is already active changes nothing.
    CalendarException("friday", date(2026, 11, 6), 1),
]


@pytest.mark.spec("gtfs_import.AC-14")
@pytest.mark.parametrize(
    ("day", "expected"),
    [
        # Wednesday inside the range: weekday services only.
        (date(2026, 11, 4), {"weekday"}),
        # Friday: only the Friday service (weekday flag not set for Fridays).
        (date(2026, 11, 6), {"friday"}),
        # Range boundaries are inclusive.
        (date(2026, 10, 16), {"friday"}),
        (date(2026, 11, 3), {"weekday", "short"}),
        # Before / after the calendar range: nothing.
        (date(2026, 10, 15), set()),
        (date(2026, 11, 23), set()),
        # exception_type = 2 removes, exception_type = 1 adds.
        (date(2026, 11, 2), {"short", "holiday_EXC"}),
        # Service present only in calendar_dates.
        (date(2026, 11, 7), {"only_dates"}),
        # Sunday with no exceptions.
        (date(2026, 11, 8), set()),
    ],
)
def test_active_services_by_date(day: date, expected: set[str]) -> None:
    assert active_services(day, CALENDARS, EXCEPTIONS) == frozenset(expected)


@pytest.mark.spec("gtfs_import.AC-14")
def test_removal_wins_over_addition_only_for_its_own_date() -> None:
    exceptions = [
        CalendarException("weekday", date(2026, 11, 4), 2),
        CalendarException("weekday", date(2026, 11, 5), 1),
    ]
    assert active_services(date(2026, 11, 4), CALENDARS, exceptions) == frozenset()
    assert active_services(date(2026, 11, 5), CALENDARS, exceptions) == frozenset({"weekday"})
