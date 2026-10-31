"""Active GTFS services for a service date (pure)."""

from collections.abc import Iterable
from datetime import date

from avisabus.domain.models.network import CalendarException, ServiceCalendar

SERVICE_ADDED = 1
SERVICE_REMOVED = 2


def active_services(
    service_date: date,
    calendars: Iterable[ServiceCalendar],
    exceptions: Iterable[CalendarException],
) -> frozenset[str]:
    """Services of `calendar` running that weekday within their range, plus the
    `calendar_dates` additions (type 1) minus the removals (type 2) for that date."""
    weekday = service_date.weekday()
    active = {
        calendar.service_id
        for calendar in calendars
        if calendar.start_date <= service_date <= calendar.end_date and calendar.weekdays[weekday]
    }
    removed: set[str] = set()
    for exception in exceptions:
        if exception.date != service_date:
            continue
        if exception.exception_type == SERVICE_ADDED:
            active.add(exception.service_id)
        elif exception.exception_type == SERVICE_REMOVED:
            removed.add(exception.service_id)
    return frozenset(active - removed)
