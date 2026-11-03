"""Validity of the active GTFS feed: range and expiry status (pure)."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from avisabus.domain.errors import DomainError
from avisabus.domain.models.network import CalendarException, FeedVersion, ServiceCalendar

DEFAULT_WARNING_DAYS = 7


@dataclass(frozen=True, slots=True)
class Valid:
    """More than `warning_days` days left until `feed_end_date`."""


@dataclass(frozen=True, slots=True)
class Expiring:
    """`feed_end_date` is today or within `warning_days` days."""

    days_left: int


@dataclass(frozen=True, slots=True)
class Expired:
    """`feed_end_date` has already passed."""

    days_ago: int


FeedValidityStatus = Valid | Expiring | Expired


class MissingValidityRangeError(DomainError):
    """Neither `feed_info` nor `calendar` / `calendar_dates` provide any date."""


def feed_validity_status(
    feed: FeedVersion, today: date, warning_days: int = DEFAULT_WARNING_DAYS
) -> FeedValidityStatus:
    """`feed_end_date` is the last valid day (inclusive)."""
    days_left = (feed.end_date - today).days
    if days_left < 0:
        return Expired(days_ago=-days_left)
    if days_left <= warning_days:
        return Expiring(days_left=days_left)
    return Valid()


def feed_validity_range(
    feed_start: date | None,
    feed_end: date | None,
    calendars: Iterable[ServiceCalendar],
    exceptions: Iterable[CalendarException],
) -> tuple[date, date]:
    """Validity from `feed_info`; any missing bound falls back to the earliest start / latest
    end of `calendar` and the dates of `calendar_dates`."""
    if feed_start is not None and feed_end is not None:
        return feed_start, feed_end
    starts: list[date] = []
    ends: list[date] = []
    for calendar in calendars:
        starts.append(calendar.start_date)
        ends.append(calendar.end_date)
    for exception in exceptions:
        starts.append(exception.date)
        ends.append(exception.date)
    if feed_start is None and not starts:
        raise MissingValidityRangeError
    if feed_end is None and not ends:
        raise MissingValidityRangeError
    start = feed_start if feed_start is not None else min(starts)
    end = feed_end if feed_end is not None else max(ends)
    return start, end
