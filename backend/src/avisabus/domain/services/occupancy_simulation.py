"""Deterministic occupancy simulation (RF-14, occupancy_sensor design §3).

`occupied = clamp(round(capacity * min(1.05, hour * route * trip)), 0, capacity)`, where the
factors depend on the local hour and weekday, on the progress along the trip and on a stable
hash of the trip. No randomness and no clock: the same inputs always give the same reading.
"""

import hashlib
import math
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from avisabus.domain.models.network import TripStopTime

LOCAL_TIMEZONE = ZoneInfo("Europe/Madrid")
"""Local time of the hour table and of the GTFS service days of EMT València."""

_HOUR_BANDS: tuple[tuple[int, float], ...] = (
    # (end hour, exclusive; factor)
    (6, 0.15),
    (7, 0.40),
    (9, 1.00),
    (13, 0.60),
    (15, 0.85),
    (17, 0.60),
    (20, 0.95),
    (22, 0.45),
    (24, 0.25),
)
WEEKEND_FACTOR = 0.70
MIN_ROUTE_FACTOR = 0.15
MAX_LOAD = 1.05
_SATURDAY = 5


def hour_factor(local_dt: datetime) -> float:
    """Demand by local hour (Europe/Madrid), reduced on Saturdays and Sundays.

    Aware datetimes are converted to Europe/Madrid; naive ones are taken as local time.
    """
    local = local_dt.astimezone(LOCAL_TIMEZONE) if local_dt.tzinfo is not None else local_dt
    factor = next(value for end, value in _HOUR_BANDS if local.hour < end)
    if local.weekday() >= _SATURDAY:
        factor *= WEEKEND_FACTOR
    return factor


def route_factor(p: float) -> float:
    """Load along the trip: `max(0.15, sin(pi * p) ** 0.8)`, highest at mid route."""
    p = min(1.0, max(0.0, p))
    load: float = max(0.0, math.sin(math.pi * p)) ** 0.8
    return max(MIN_ROUTE_FACTOR, load)


def trip_factor(seed: str, trip_id: str, service_date: date) -> float:
    """`0.75 + 0.5 * u`, with `u` in [0, 1) taken from `sha256(f"{seed}:{trip_id}:{date}")`."""
    digest = hashlib.sha256(f"{seed}:{trip_id}:{service_date}".encode()).digest()
    u = int.from_bytes(digest[:8], "big") / 2**64
    return 0.75 + 0.5 * u


def simulate_occupied(capacity: int, h: float, r: float, t: float) -> int:
    occupied = round(capacity * min(MAX_LOAD, h * r * t))
    return min(capacity, max(0, occupied))


def progress(trip_stop_times: Sequence[TripStopTime], service_date: date, at: datetime) -> float:
    """Share of the scheduled trip elapsed at `at`, clamped to [0, 1].

    `p = (s_at - s_first) / (s_last - s_first)`, with the `arrival_s` of the first and last
    stops and `s_at` the seconds of `at` since the start of the service day.
    """
    if not trip_stop_times:
        raise ValueError("a trip without stop times has no progress")
    ordered = sorted(trip_stop_times, key=lambda stop_time: stop_time.stop_sequence)
    first, last = ordered[0].arrival_s, ordered[-1].arrival_s
    elapsed = (at - service_day_start(service_date)).total_seconds()
    if last <= first:
        return 1.0 if elapsed >= first else 0.0
    return min(1.0, max(0.0, (elapsed - first) / (last - first)))


def service_day_start(service_date: date) -> datetime:
    """GTFS: the service day starts at local noon minus 12 h. Returned in UTC."""
    noon = datetime(
        service_date.year, service_date.month, service_date.day, 12, tzinfo=LOCAL_TIMEZONE
    )
    return noon.astimezone(UTC) - timedelta(hours=12)
