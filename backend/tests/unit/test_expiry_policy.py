"""`expiry_reason` (`NEXT_STOP`, `TIMEOUT`) and the scheduled time at the next stop (T-01).

The current instant comes from a `FakeClock`, as the ticker reads it.
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from avisabus.domain.models.alert import Alert, AlertStatus, AlertTracking, ExpiryReason, Need
from avisabus.domain.models.network import TripStopTime
from avisabus.domain.services.expiry_policy import (
    DEFAULT_NEXT_STOP_MARGIN,
    expiry_reason,
    next_stop_scheduled_at,
)
from avisabus.domain.services.occupancy_simulation import service_day_start
from tests.support.fake_clock import FakeClock

DAY = date(2026, 11, 2)
CREATED = datetime(2026, 11, 2, 19, 48, 3, tzinfo=UTC)
NEXT_STOP_AT = datetime(2026, 11, 2, 19, 56, 0, tzinfo=UTC)
DELAY_S = 150


def alert(delay_s: int = DELAY_S, **changes: object) -> Alert:
    base = Alert(
        alert_id="6f1c0d6e-3b9a-4c2e-9f4d-2a7b8c9d0e1f",
        device_hash="d" * 64,
        stop_id="508",
        stop_name="Parc de l'Oest - Enguera",
        line="93",
        direction_id=0,
        destination="Passeig Marítim - Hospital Malva-rosa",
        trip_id="93_122",
        service_date=DAY,
        stop_sequence=12,
        needs=(Need.RAMP,),
        status=AlertStatus.PENDING_DRIVER,
        delivered_to=None,
        created_at=CREATED,
        expires_at=CREATED + timedelta(minutes=30),
        tracking=AlertTracking(CREATED, CREATED + timedelta(minutes=5), delay_s),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def due() -> datetime:
    """Earliest `NEXT_STOP`: next stop's scheduled time + last delay + margin."""
    return NEXT_STOP_AT + timedelta(seconds=DELAY_S) + DEFAULT_NEXT_STOP_MARGIN


def test_the_default_margin_is_two_minutes() -> None:
    assert timedelta(minutes=2) == DEFAULT_NEXT_STOP_MARGIN


# --- Next stop (AC-05) ---


@pytest.mark.spec("alert_expiry.AC-05")
@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        pytest.param(timedelta(seconds=-1), None, id="one-second-before"),
        pytest.param(timedelta(0), ExpiryReason.NEXT_STOP, id="at-the-limit"),
        pytest.param(timedelta(minutes=3), ExpiryReason.NEXT_STOP, id="after"),
    ],
)
def test_a_trip_not_seen_lately_expires_once_it_should_be_at_the_next_stop(
    offset: timedelta, expected: ExpiryReason | None
) -> None:
    clock = FakeClock(due() + offset)
    result = expiry_reason(alert(), clock.now(), NEXT_STOP_AT, seen_in_last_observation=False)
    assert result == expected


@pytest.mark.spec("alert_expiry.AC-05")
def test_a_trip_in_the_last_observation_does_not_expire_by_next_stop() -> None:
    """With a recent observation that includes it, the bus has not passed yet."""
    clock = FakeClock(due() + timedelta(minutes=5))
    assert expiry_reason(alert(), clock.now(), NEXT_STOP_AT, seen_in_last_observation=True) is None


@pytest.mark.spec("alert_expiry.AC-05")
def test_the_last_stop_of_the_trip_never_expires_by_next_stop() -> None:
    clock = FakeClock(due() + timedelta(minutes=5))
    assert expiry_reason(alert(), clock.now(), None, seen_in_last_observation=False) is None


@pytest.mark.spec("alert_expiry.AC-05")
@pytest.mark.parametrize("delay_s", [-300, 0, 420])
def test_the_last_observed_delay_moves_the_limit(delay_s: int) -> None:
    limit = NEXT_STOP_AT + timedelta(seconds=delay_s) + DEFAULT_NEXT_STOP_MARGIN
    before = expiry_reason(alert(delay_s), limit - timedelta(seconds=1), NEXT_STOP_AT, False)
    at_limit = expiry_reason(alert(delay_s), limit, NEXT_STOP_AT, False)
    assert (before, at_limit) == (None, ExpiryReason.NEXT_STOP)


@pytest.mark.spec("alert_expiry.AC-05")
def test_the_margin_is_configurable() -> None:
    margin = timedelta(minutes=5)
    limit = NEXT_STOP_AT + timedelta(seconds=DELAY_S) + margin
    assert expiry_reason(alert(), limit - timedelta(seconds=1), NEXT_STOP_AT, False, margin) is None
    assert expiry_reason(alert(), limit, NEXT_STOP_AT, False, margin) is ExpiryReason.NEXT_STOP


# --- Timeout (AC-06) ---


@pytest.mark.spec("alert_expiry.AC-06")
@pytest.mark.parametrize(
    ("offset", "expected"),
    [
        pytest.param(timedelta(seconds=-1), None, id="one-second-before"),
        pytest.param(timedelta(0), ExpiryReason.TIMEOUT, id="at-expires-at"),
        pytest.param(timedelta(hours=2), ExpiryReason.TIMEOUT, id="long-after"),
    ],
)
def test_every_alert_expires_at_its_expiry_time(
    offset: timedelta, expected: ExpiryReason | None
) -> None:
    one = alert()
    clock = FakeClock(one.expires_at + offset)
    # Last stop of the trip and seen lately: only the timeout applies.
    assert expiry_reason(one, clock.now(), None, seen_in_last_observation=True) == expected


@pytest.mark.spec("alert_expiry.AC-06")
def test_the_timeout_applies_while_the_trip_is_still_seen() -> None:
    one = alert()
    clock = FakeClock(one.expires_at)
    result = expiry_reason(one, clock.now(), NEXT_STOP_AT, seen_in_last_observation=True)
    assert result is ExpiryReason.TIMEOUT


# --- Priority (AC-07) ---


@pytest.mark.spec("alert_expiry.AC-07")
def test_next_stop_comes_before_timeout() -> None:
    one = alert(expires_at=due())
    clock = FakeClock(due())
    result = expiry_reason(one, clock.now(), NEXT_STOP_AT, seen_in_last_observation=False)
    assert result is ExpiryReason.NEXT_STOP


# --- Scheduled time at the next stop ---


def stop_time(stop_id: str, sequence: int, arrival_s: int) -> TripStopTime:
    return TripStopTime(stop_id, sequence, arrival_s, arrival_s, None)


TRIP = [
    stop_time("100", 1, 19 * 3600),
    stop_time("508", 2, 19 * 3600 + 300),
    stop_time("200", 3, 19 * 3600 + 420),
    stop_time("508", 4, 19 * 3600 + 900),  # circular: the stop again
    stop_time("300", 5, 19 * 3600 + 1000),
]


@pytest.mark.spec("alert_expiry.AC-05")
def test_the_next_stop_is_the_entry_after_the_alert_occurrence() -> None:
    start = service_day_start(DAY)
    assert next_stop_scheduled_at(TRIP, 2, DAY) == start + timedelta(seconds=19 * 3600 + 420)
    assert next_stop_scheduled_at(TRIP, 4, DAY) == start + timedelta(seconds=19 * 3600 + 1000)


@pytest.mark.spec("alert_expiry.AC-05")
def test_the_next_stop_does_not_depend_on_the_order_given() -> None:
    start = service_day_start(DAY)
    shuffled = list(reversed(TRIP))
    assert next_stop_scheduled_at(shuffled, 2, DAY) == start + timedelta(seconds=19 * 3600 + 420)


@pytest.mark.spec("alert_expiry.AC-05")
def test_the_last_stop_has_no_next_stop() -> None:
    assert next_stop_scheduled_at(TRIP, 5, DAY) is None
    assert next_stop_scheduled_at([], 2, DAY) is None


@pytest.mark.spec("alert_expiry.AC-05")
def test_service_day_hours_beyond_24_are_the_next_civil_day() -> None:
    """A night trip of 2 November whose next stop is at 25:10:00 (01:10 on 3 November in
    València, 00:10 UTC)."""
    trip = [stop_time("508", 7, 24 * 3600 + 3000), stop_time("200", 8, 25 * 3600 + 600)]
    assert next_stop_scheduled_at(trip, 7, DAY) == datetime(2026, 11, 3, 0, 10, tzinfo=UTC)


@pytest.mark.spec("alert_expiry.AC-05")
def test_service_day_start_follows_the_daylight_saving_change() -> None:
    """25 October 2026 (end of summer time in Madrid): noon − 12 h is 23:00 UTC of the day
    before, so 12:00:00 of service time is 11:00 UTC."""
    day = date(2026, 10, 25)
    trip = [stop_time("508", 1, 11 * 3600), stop_time("200", 2, 12 * 3600)]
    assert next_stop_scheduled_at(trip, 1, day) == datetime(2026, 10, 25, 11, 0, tzinfo=UTC)
