"""Expiry of an alert by time: next stop and max age (alert_expiry design §3, CU-07 1a/1b).

`PASSED` is decided by `observe_passage` with each SAE observation. AC-07 (`PASSED` before
`NEXT_STOP` before `TIMEOUT`) holds because the passage watcher expires first and an alert that
is already deleted is not expired again.
"""

from collections.abc import Iterable
from datetime import date, datetime, timedelta

from avisabus.domain.models.alert import Alert, ExpiryReason
from avisabus.domain.models.network import TripStopTime
from avisabus.domain.services.occupancy_simulation import service_day_start

DEFAULT_NEXT_STOP_MARGIN = timedelta(minutes=2)


def expiry_reason(
    alert: Alert,
    now: datetime,
    next_stop_scheduled_at: datetime | None,
    seen_in_last_observation: bool,
    next_stop_margin: timedelta = DEFAULT_NEXT_STOP_MARGIN,
) -> ExpiryReason | None:
    """`NEXT_STOP` when the trip has a next stop, the last REALTIME observation of the stop did
    not include it and `now ≥ next stop + last delay + margin` (AC-05); else `TIMEOUT` once
    `now ≥ expires_at` (AC-06); else `None`."""
    if (
        next_stop_scheduled_at is not None
        and not seen_in_last_observation
        and now
        >= next_stop_scheduled_at
        + timedelta(seconds=alert.tracking.last_delay_s)
        + next_stop_margin
    ):
        return ExpiryReason.NEXT_STOP
    if now >= alert.expires_at:
        return ExpiryReason.TIMEOUT
    return None


def next_stop_scheduled_at(
    stop_times: Iterable[TripStopTime], stop_sequence: int, service_date: date
) -> datetime | None:
    """Scheduled arrival at the stop that follows the occurrence `stop_sequence` in the trip:
    start of the service day (noon − 12 h) + its `arrival_s`, which may exceed 24 h. `None` when
    that occurrence is the last stop of the trip."""
    following = [stop for stop in stop_times if stop.stop_sequence > stop_sequence]
    if not following:
        return None
    next_stop = min(following, key=lambda stop: stop.stop_sequence)
    return service_day_start(service_date) + timedelta(seconds=next_stop.arrival_s)
