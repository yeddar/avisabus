"""Alert model, needs and alert errors (alert_create T-02)."""

from datetime import UTC, date, datetime, timedelta

import pytest

from avisabus.domain.errors import BusNotRequestableError, DomainError, RateLimitedError
from avisabus.domain.models.alert import (
    NEED_ORDER,
    Alert,
    AlertStatus,
    AlertTracking,
    Need,
    canonical_needs,
)

NOW = datetime(2026, 11, 4, 7, 40, tzinfo=UTC)


@pytest.mark.spec("alert_create.AC-06")
def test_needs_and_their_canonical_order() -> None:
    assert [need.value for need in Need] == ["RAMP", "EXTRA_TIME", "SEAT", "VISUAL"]
    assert NEED_ORDER == (Need.RAMP, Need.EXTRA_TIME, Need.SEAT, Need.VISUAL)


@pytest.mark.spec("alert_create.AC-06")
@pytest.mark.parametrize(
    ("needs", "expected"),
    [
        ([], ()),
        ([Need.VISUAL, Need.RAMP], (Need.RAMP, Need.VISUAL)),
        (
            [Need.SEAT, Need.VISUAL, Need.EXTRA_TIME, Need.RAMP],
            (Need.RAMP, Need.EXTRA_TIME, Need.SEAT, Need.VISUAL),
        ),
    ],
)
def test_canonical_needs_sorts_them(needs: list[Need], expected: tuple[Need, ...]) -> None:
    assert canonical_needs(needs) == expected


@pytest.mark.spec("alert_create.AC-06")
def test_canonical_needs_rejects_repeated_needs() -> None:
    with pytest.raises(ValueError, match="repeated"):
        canonical_needs([Need.SEAT, Need.RAMP, Need.SEAT])


def test_alert_statuses() -> None:
    assert [status.value for status in AlertStatus] == ["PENDING_DRIVER", "DELIVERED"]


def test_alert_is_an_immutable_value() -> None:
    tracking = AlertTracking(last_seen_at=None, last_arrival_at=NOW, last_delay_s=0)
    alert = Alert(
        alert_id="a",
        device_hash="h",
        stop_id="508",
        stop_name="Parc de l'Oest - Enguera",
        line="93",
        direction_id=0,
        destination="Passeig Marítim - Hospital Malva-rosa",
        trip_id="t",
        service_date=date(2026, 11, 4),
        stop_sequence=5,
        needs=(Need.RAMP,),
        status=AlertStatus.PENDING_DRIVER,
        delivered_to=None,
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=30),
        tracking=tracking,
    )
    with pytest.raises(AttributeError):
        alert.status = AlertStatus.DELIVERED  # type: ignore[misc]


@pytest.mark.spec("alert_create.AC-08")
def test_alert_errors_carry_no_identifiers_in_their_message() -> None:
    limited = RateLimitedError(retry_after_s=42)
    assert limited.retry_after_s == 42
    assert str(limited) == "rate limited"
    assert str(BusNotRequestableError()) == "bus not requestable"
    assert isinstance(limited, DomainError)
    assert isinstance(BusNotRequestableError(), DomainError)
