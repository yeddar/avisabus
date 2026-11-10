"""Demand of the next stops and capacity alerts of a driver (driver_demand design §3, RF-29)."""

from collections.abc import Sequence

from avisabus.domain.models.alert import Alert, Need
from avisabus.domain.models.driver import UpcomingStop
from avisabus.domain.models.driver_view import NeedCounts, StopDemand


def stop_demand(
    upcoming: Sequence[UpcomingStop], alerts: Sequence[Alert]
) -> tuple[StopDemand, ...]:
    """Requests per stop. A request counts in a stop only in its own occurrence of it (a circular
    trip calls twice at some stops), so both the stop and its sequence must match."""
    return tuple(_demand_of(stop, alerts) for stop in upcoming)


def _demand_of(stop: UpcomingStop, alerts: Sequence[Alert]) -> StopDemand:
    matching = [
        alert
        for alert in alerts
        if alert.stop_id == stop.stop_id and alert.stop_sequence == stop.stop_sequence
    ]

    def count(need: Need) -> int:
        return sum(need in alert.needs for alert in matching)

    return StopDemand(
        stop_id=stop.stop_id,
        name=stop.name,
        stop_sequence=stop.stop_sequence,
        distance_m=stop.distance_m,
        waiting=len(matching),
        needs=NeedCounts(
            RAMP=count(Need.RAMP),
            EXTRA_TIME=count(Need.EXTRA_TIME),
            SEAT=count(Need.SEAT),
            VISUAL=count(Need.VISUAL),
        ),
        alert_ids=tuple(alert.alert_id for alert in matching),
    )


def capacity_flags(
    stops: Sequence[StopDemand], free_places: int | None, free_seats: int | None
) -> tuple[bool, bool]:
    """(capacity_alert, seat_alert); each is `False` when its figure is unknown (AC-06)."""
    waiting = sum(stop.waiting for stop in stops)
    seats = sum(stop.needs.SEAT for stop in stops)
    return (
        free_places is not None and waiting > free_places,
        free_seats is not None and seats > free_seats,
    )
