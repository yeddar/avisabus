"""Passage of the alert's bus by its stop, seen only with the SAE (alert_expiry design §3, D12).

The alert follows its GTFS trip (ADR-016) in the real-time arrivals of the stop. When the trip
disappears and, in the last observation that had it, it was arriving within the window, the bus
has passed. A trip that disappears while still far away is not taken as passed (LIM-02: better
late than early); `NEXT_STOP` or `TIMEOUT` will expire it.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from avisabus.domain.models.alert import AlertTracking, ExpiryReason

DEFAULT_PASSAGE_WINDOW = timedelta(minutes=2)
"""Validated with the real session `stop_508_peak` (exploration E-01)."""


@dataclass(frozen=True, slots=True)
class PassageObservation:
    """The alert's trip in one REALTIME observation of its stop."""

    trip_present: bool
    arrival_at: datetime | None = None
    """Its arrival, when present."""
    delay_s: int | None = None
    """`arrival_at` − scheduled time at the alert's occurrence of the stop (`stop_sequence`);
    `None` when present but that occurrence is no longer in the active feed."""


def observe_passage(
    tracking: AlertTracking,
    observation: PassageObservation,
    observed_at: datetime,
    passage_window: timedelta = DEFAULT_PASSAGE_WINDOW,
) -> AlertTracking | ExpiryReason | None:
    """The new tracking when the trip is present (AC-01); `PASSED` when it is absent and, when
    last seen, it was arriving within `passage_window`, inclusive (AC-02); otherwise `None`
    (nothing changes: absent while far away, or never seen in real time)."""
    if observation.trip_present:
        if observation.arrival_at is None:
            raise ValueError("a present trip needs its arrival")
        delay_s = tracking.last_delay_s if observation.delay_s is None else observation.delay_s
        return AlertTracking(
            last_seen_at=observed_at,
            last_arrival_at=observation.arrival_at,
            last_delay_s=delay_s,
        )
    if (
        tracking.last_seen_at is not None
        and tracking.last_arrival_at - tracking.last_seen_at <= passage_window
    ):
        return ExpiryReason.PASSED
    return None
