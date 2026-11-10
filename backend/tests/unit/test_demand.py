"""Demand of the next stops and capacity alerts (driver_demand T-01)."""

import pytest

from avisabus.domain.models.alert import Need
from avisabus.domain.models.driver import UpcomingStop
from avisabus.domain.models.driver_view import NeedCounts, StopDemand
from avisabus.domain.services.demand import capacity_flags, stop_demand
from tests.support.demand import alert_at


def _stop(stop_id: str, sequence: int) -> UpcomingStop:
    return UpcomingStop(stop_id, f"Stop {stop_id}", sequence, 100.0 * sequence)


def _demand(waiting: int, seats: int) -> StopDemand:
    return StopDemand("s", "Stop", 1, 0.0, waiting, NeedCounts(SEAT=seats), ())


@pytest.mark.spec("driver_demand.AC-05")
def test_counts_requests_and_needs_of_each_stop() -> None:
    upcoming = [_stop("s1", 2), _stop("s2", 3)]
    alerts = [
        alert_at(1, "s1", 2, (Need.RAMP, Need.SEAT)),
        alert_at(2, "s1", 2, (Need.RAMP,)),
        alert_at(3, "s2", 3, (Need.EXTRA_TIME, Need.VISUAL)),
    ]

    first, second = stop_demand(upcoming, alerts)

    assert first == StopDemand(
        stop_id="s1",
        name="Stop s1",
        stop_sequence=2,
        distance_m=200.0,
        waiting=2,
        needs=NeedCounts(RAMP=2, SEAT=1),
        alert_ids=("alert-1", "alert-2"),
    )
    assert second.waiting == 1
    assert second.needs == NeedCounts(EXTRA_TIME=1, VISUAL=1)
    assert second.alert_ids == ("alert-3",)


@pytest.mark.spec("driver_demand.AC-05")
def test_a_request_only_counts_in_its_occurrence_of_the_stop() -> None:
    upcoming = [_stop("loop", 2), _stop("s2", 3), _stop("loop", 9)]
    alerts = [alert_at(1, "loop", 9, (Need.SEAT,))]

    first, second, third = stop_demand(upcoming, alerts)

    assert (first.waiting, second.waiting, third.waiting) == (0, 0, 1)
    assert first.alert_ids == ()
    assert first.needs == NeedCounts()
    assert third.alert_ids == ("alert-1",)


@pytest.mark.spec("driver_demand.AC-05")
def test_a_request_of_a_stop_not_shown_is_ignored() -> None:
    assert stop_demand([_stop("s1", 2)], [alert_at(1, "other", 7)])[0].waiting == 0


@pytest.mark.spec("driver_demand.AC-05")
def test_no_upcoming_stops_means_no_demand() -> None:
    assert stop_demand([], [alert_at(1)]) == ()


@pytest.mark.spec("driver_demand.AC-06")
@pytest.mark.parametrize(
    ("waiting", "seats", "free_places", "free_seats", "expected"),
    [
        (2, 0, 30, 4, (False, False)),
        (3, 0, 3, 4, (False, False)),  # equal places: nobody is left out
        (4, 0, 3, 4, (True, False)),
        (0, 0, 0, 0, (False, False)),
        (1, 1, 1, 0, (False, True)),
        (5, 3, 1, 2, (True, True)),
        (3, 3, 3, 3, (False, False)),
        (2, 2, None, None, (False, False)),  # no data: never an alert
        (2, 2, 1, None, (True, False)),
        (2, 2, None, 1, (False, True)),
    ],
)
def test_capacity_flags(
    waiting: int,
    seats: int,
    free_places: int | None,
    free_seats: int | None,
    expected: tuple[bool, bool],
) -> None:
    assert capacity_flags([_demand(waiting, seats)], free_places, free_seats) == expected


@pytest.mark.spec("driver_demand.AC-06")
def test_capacity_flags_add_up_every_stop_shown() -> None:
    stops = [_demand(2, 1), _demand(2, 1)]

    assert capacity_flags(stops, 3, 1) == (True, True)
    assert capacity_flags(stops, 4, 2) == (False, False)
