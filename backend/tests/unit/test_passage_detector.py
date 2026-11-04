"""`observe_passage`: tracking of the alert's trip and passage detection with the SAE (T-01).

Pure function: the observation instant is given (`StopArrivals.generated_at` in the watcher).
"""

from datetime import UTC, datetime, timedelta

import pytest

from avisabus.domain.models.alert import AlertTracking, ExpiryReason
from avisabus.domain.services.passage_detector import (
    DEFAULT_PASSAGE_WINDOW,
    PassageObservation,
    observe_passage,
)

SEEN = datetime(2026, 11, 2, 19, 55, 3, tzinfo=UTC)
NOW = SEEN + timedelta(seconds=15)


def tracking(lead: timedelta | None, delay_s: int = 120) -> AlertTracking:
    """Last seen at `SEEN` arriving `lead` later; `None`: never seen in real time."""
    if lead is None:
        return AlertTracking(None, SEEN + timedelta(minutes=5), delay_s)
    return AlertTracking(SEEN, SEEN + lead, delay_s)


ABSENT = PassageObservation(trip_present=False, arrival_at=None, delay_s=None)


def test_the_default_window_is_two_minutes() -> None:
    assert timedelta(minutes=2) == DEFAULT_PASSAGE_WINDOW


# --- The trip appears: tracking (AC-01) ---


@pytest.mark.spec("alert_expiry.AC-01")
@pytest.mark.parametrize("previous", [None, timedelta(minutes=9), timedelta(0)])
def test_a_present_trip_updates_its_tracking(previous: timedelta | None) -> None:
    arrival = NOW + timedelta(minutes=4)
    observation = PassageObservation(trip_present=True, arrival_at=arrival, delay_s=95)
    result = observe_passage(tracking(previous), observation, NOW)
    assert result == AlertTracking(last_seen_at=NOW, last_arrival_at=arrival, last_delay_s=95)


@pytest.mark.spec("alert_expiry.AC-01")
@pytest.mark.spec("alert_expiry.AC-07")
def test_a_present_trip_never_passes_even_arriving_now() -> None:
    """Present with a lead ≤ the window (or even in the past): tracking, not `PASSED`."""
    for lead in (timedelta(0), timedelta(seconds=-15), timedelta(minutes=1)):
        observation = PassageObservation(trip_present=True, arrival_at=NOW + lead, delay_s=10)
        result = observe_passage(tracking(timedelta(minutes=1)), observation, NOW)
        assert result == AlertTracking(NOW, NOW + lead, 10)


@pytest.mark.spec("alert_expiry.AC-01")
def test_a_present_trip_without_a_known_delay_keeps_the_previous_one() -> None:
    """The trip no longer calls at the alert's occurrence (the active feed changed in between)."""
    arrival = NOW + timedelta(minutes=3)
    observation = PassageObservation(trip_present=True, arrival_at=arrival, delay_s=None)
    result = observe_passage(tracking(timedelta(minutes=5), delay_s=-40), observation, NOW)
    assert result == AlertTracking(NOW, arrival, -40)


def test_a_present_trip_needs_its_arrival() -> None:
    with pytest.raises(ValueError, match="arrival"):
        observe_passage(tracking(None), PassageObservation(trip_present=True, arrival_at=None), NOW)


# --- The trip is absent: passage (AC-02) ---


@pytest.mark.spec("alert_expiry.AC-02")
@pytest.mark.parametrize(
    ("last_lead", "expected"),
    [
        pytest.param(timedelta(0), ExpiryReason.PASSED, id="0-min"),
        pytest.param(timedelta(seconds=-15), ExpiryReason.PASSED, id="already-due-from-cache"),
        pytest.param(timedelta(seconds=105), ExpiryReason.PASSED, id="2-min-from-cache"),
        pytest.param(timedelta(minutes=2), ExpiryReason.PASSED, id="2-min-inclusive"),
        pytest.param(timedelta(minutes=2, seconds=1), None, id="just-over-2-min"),
        pytest.param(timedelta(minutes=3), None, id="3-min"),
        pytest.param(timedelta(minutes=27), None, id="far-away"),
        pytest.param(None, None, id="never-seen"),
    ],
)
def test_an_absent_trip_has_passed_only_if_it_was_arriving_within_the_window(
    last_lead: timedelta | None, expected: ExpiryReason | None
) -> None:
    assert observe_passage(tracking(last_lead), ABSENT, NOW) == expected


@pytest.mark.spec("alert_expiry.AC-02")
@pytest.mark.parametrize(
    ("window", "last_lead", "expected"),
    [
        (timedelta(minutes=1), timedelta(minutes=2), None),
        (timedelta(minutes=1), timedelta(minutes=1), ExpiryReason.PASSED),
        (timedelta(minutes=3), timedelta(minutes=3), ExpiryReason.PASSED),
        (timedelta(minutes=3), timedelta(minutes=4), None),
    ],
)
def test_the_window_is_configurable(
    window: timedelta, last_lead: timedelta, expected: ExpiryReason | None
) -> None:
    assert observe_passage(tracking(last_lead), ABSENT, NOW, passage_window=window) == expected


@pytest.mark.spec("alert_expiry.AC-02")
def test_the_lead_is_measured_at_the_last_observation_not_now() -> None:
    """`last_arrival_at − last_seen_at`: much later, a trip that was 1 min away has passed, and
    one that was 5 min away has not, although both arrival times are long gone."""
    later = SEEN + timedelta(minutes=20)
    assert observe_passage(tracking(timedelta(minutes=1)), ABSENT, later) is ExpiryReason.PASSED
    assert observe_passage(tracking(timedelta(minutes=5)), ABSENT, later) is None
