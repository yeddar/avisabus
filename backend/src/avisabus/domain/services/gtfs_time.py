"""GTFS times (`HH:MM:SS`, hours may be >= 24) as seconds since the start of the service day."""

import re

from avisabus.domain.errors import DomainError

_GTFS_TIME = re.compile(r"^(\d{1,3}):([0-5]\d):([0-5]\d)$")


class InvalidGtfsTimeError(DomainError):
    """The value is not a GTFS time (`H:MM:SS` or `HH:MM:SS`)."""


def parse_gtfs_time(value: str) -> int:
    """Parse `"25:10:00"` into `90600`. Hours >= 24 belong to the same service day."""
    match = _GTFS_TIME.match(value.strip())
    if match is None:
        raise InvalidGtfsTimeError(value)
    hours, minutes, seconds = (int(part) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


def format_gtfs_time(seconds: int) -> str:
    """Inverse of `parse_gtfs_time`: `90600` -> `"25:10:00"`."""
    if seconds < 0:
        raise InvalidGtfsTimeError(str(seconds))
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
