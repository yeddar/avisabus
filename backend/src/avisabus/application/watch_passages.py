"""Passage watcher: one cycle of the `PassageWatcher` task (alert_expiry design §3).

Each cycle groups the active alerts by stop and asks each stop's arrivals **once**, through
`GetStopArrivals` and its SAE cache (AC-04, RNF-08). With a REALTIME observation, each alert's
trip (`trip_id` + `service_date`) is looked for among the paired arrivals: present, its tracking
is updated and stored (AC-01, AC-09); absent, `observe_passage` decides whether it has passed
(AC-02). A SCHEDULED observation (SAE unavailable) changes nothing (AC-03, D12).

The observation instant is `StopArrivals.generated_at`, read from the same `Clock` as the cycle
(exploration E-01; alert_create stores it as `last_seen_at` too).

It also remembers, in memory and per alert, whether the trip was in the last REALTIME observation
of its stop (`seen_in_last_observation`), which `ExpireDueAlerts` reads for `NEXT_STOP` (AC-05).
After a restart it is `False` until the first observation.
"""

from collections import defaultdict
from collections.abc import Sequence
from datetime import timedelta
from typing import Any, Protocol

from avisabus.application.expire_alert import ExpireAlert
from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.domain.errors import NoActiveFeedError, StopNotFoundError
from avisabus.domain.models.alert import Alert, AlertTracking, ExpiryReason
from avisabus.domain.models.network import TripStopTime
from avisabus.domain.models.stop_arrivals import ArrivalSource, ArrivalView, StopArrivals
from avisabus.domain.ports.alerts import AlertRepository
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.occupancy_simulation import service_day_start
from avisabus.domain.services.passage_detector import PassageObservation, observe_passage

TRIP_LOST = "alert.trip_lost"
STOP_SKIPPED = "passage.stop_skipped"


class Logger(Protocol):
    def debug(self, event: str, **fields: Any) -> Any: ...

    def info(self, event: str, **fields: Any) -> Any: ...

    def warning(self, event: str, **fields: Any) -> Any: ...


class WatchPassages:
    def __init__(
        self,
        alerts: AlertRepository,
        stop_arrivals: GetStopArrivals,
        network: NetworkRepository,
        expire: ExpireAlert,
        clock: Clock,
        logger: Logger,
        passage_window: timedelta,
    ) -> None:
        self._alerts = alerts
        self._stop_arrivals = stop_arrivals
        self._network = network
        self._expire = expire
        self._clock = clock  # `GetStopArrivals` reads it: `generated_at` is the cycle's instant
        self._log = logger
        self._window = passage_window
        self._seen: dict[str, bool] = {}

    def seen_in_last_observation(self, alert_id: str) -> bool:
        """Whether the alert's trip was in the last REALTIME observation of its stop; `False`
        if that observation was SCHEDULED or there is none yet."""
        return self._seen.get(alert_id, False)

    async def tick(self) -> None:
        """Raises only what is not a stop that cannot be read (the periodic task logs it)."""
        alerts = self._alerts.list_all()
        active = {alert.alert_id for alert in alerts}
        for alert_id in [alert_id for alert_id in self._seen if alert_id not in active]:
            del self._seen[alert_id]

        by_stop: dict[str, list[Alert]] = defaultdict(list)
        for alert in alerts:
            by_stop[alert.stop_id].append(alert)
        stop_times: dict[str, list[TripStopTime]] = {}
        for stop_id, at_stop in by_stop.items():
            try:
                arrivals = await self._stop_arrivals.for_stop(stop_id)
            except (StopNotFoundError, NoActiveFeedError) as error:
                self._log.warning(STOP_SKIPPED, stop_id=stop_id, error_type=type(error).__name__)
                continue
            for alert in at_stop:
                if arrivals.source is ArrivalSource.REALTIME:
                    self._observe(alert, arrivals, stop_times)
                else:  # the SAE is unavailable: no tracking, no passage (AC-03)
                    self._seen[alert.alert_id] = False

    def _observe(
        self, alert: Alert, arrivals: StopArrivals, stop_times: dict[str, list[TripStopTime]]
    ) -> None:
        arrival = _trip_arrival(alert, arrivals)
        if arrival is None:
            observation = PassageObservation(trip_present=False)
        else:
            if alert.trip_id not in stop_times:
                stop_times[alert.trip_id] = self._network.trip_stop_times(alert.trip_id)
            observation = PassageObservation(
                trip_present=True,
                arrival_at=arrival.arrival_at,
                delay_s=_delay_s(alert, arrival, stop_times[alert.trip_id]),
            )
        self._seen[alert.alert_id] = arrival is not None
        result = observe_passage(alert.tracking, observation, arrivals.generated_at, self._window)
        if isinstance(result, AlertTracking):
            self._alerts.update_tracking(alert.alert_id, result)
        elif result is ExpiryReason.PASSED:
            self._expire(alert, ExpiryReason.PASSED)
            self._seen.pop(alert.alert_id, None)
        else:  # absent, far away or never seen in real time: kept (LIM-02)
            self._log.debug(TRIP_LOST, alert_id=alert.alert_id, stop_id=alert.stop_id)


def _trip_arrival(alert: Alert, arrivals: StopArrivals) -> ArrivalView | None:
    """The first arrival paired with the alert's trip on its service day."""
    return next(
        (
            arrival
            for arrival in arrivals.arrivals
            if arrival.vehicle is not None
            and arrival.vehicle.trip_id == alert.trip_id
            and arrival.vehicle.service_date == alert.service_date
        ),
        None,
    )


def _delay_s(alert: Alert, arrival: ArrivalView, stop_times: Sequence[TripStopTime]) -> int | None:
    """`arrival_at` − scheduled time at the alert's occurrence of the stop, in whole seconds;
    `None` if the active feed no longer has that occurrence."""
    occurrence = next(
        (
            stop_time
            for stop_time in stop_times
            if stop_time.stop_sequence == alert.stop_sequence and stop_time.stop_id == alert.stop_id
        ),
        None,
    )
    if occurrence is None:
        return None
    scheduled = service_day_start(alert.service_date) + timedelta(seconds=occurrence.arrival_s)
    return round((arrival.arrival_at - scheduled).total_seconds())
