"""Normalised arrivals model, port and error (sae_arrivals_source T-01)."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from avisabus.domain.errors import ArrivalsUnavailableError, DomainError
from avisabus.domain.models.arrivals import ArrivalKind, ArrivalsSnapshot, SaeArrival
from avisabus.domain.ports.arrivals import ArrivalsSource

FETCHED_AT = datetime(2026, 11, 2, 11, 0, 11, tzinfo=UTC)


def _arrival() -> SaeArrival:
    return SaeArrival(
        line="93",
        destination="Pass. Marítim",
        kind=ArrivalKind.MINUTES,
        minutes=5,
        arrival_at=FETCHED_AT + timedelta(minutes=5),
    )


def test_snapshot_is_an_immutable_value_object() -> None:
    snapshot = ArrivalsSnapshot(stop_id="508", fetched_at=FETCHED_AT, arrivals=(_arrival(),))
    assert snapshot == ArrivalsSnapshot("508", FETCHED_AT, (_arrival(),))
    with pytest.raises(dataclasses.FrozenInstanceError):
        snapshot.stop_id = "2070"  # type: ignore[misc]


def test_arrival_kinds_are_minutes_and_clock_time() -> None:
    assert [kind.value for kind in ArrivalKind] == ["MINUTES", "CLOCK_TIME"]


def test_unavailable_error_keeps_stop_and_reason_as_attributes() -> None:
    error = ArrivalsUnavailableError("508", "timeout")
    assert isinstance(error, DomainError)
    assert (error.stop_id, error.reason) == ("508", "timeout")
    assert "508" not in str(error)  # identifiers go in attributes, not in the message


async def test_a_class_with_get_arrivals_satisfies_the_port() -> None:
    class Static:
        async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
            return ArrivalsSnapshot(stop_id, FETCHED_AT, ())

    source: ArrivalsSource = Static()
    assert (await source.get_arrivals("508")).arrivals == ()
