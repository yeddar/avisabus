"""Expiry by time: one cycle of the `AlertExpiryTicker` task (alert_expiry design §3).

For each active alert: `NEXT_STOP` when its bus should already be at the next stop of its trip
and the last REALTIME observation of its stop did not include it (AC-05), else `TIMEOUT` at
`expires_at` (AC-06). `PASSED` is the watcher's; an alert it already deleted is not listed, and
`ExpireAlert` ignores one deleted in between (AC-07).
"""

from collections.abc import Callable
from datetime import timedelta

from avisabus.application.expire_alert import ExpireAlert
from avisabus.domain.models.network import TripStopTime
from avisabus.domain.ports.alerts import AlertRepository
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.expiry_policy import expiry_reason, next_stop_scheduled_at


class ExpireDueAlerts:
    def __init__(
        self,
        alerts: AlertRepository,
        network: NetworkRepository,
        expire: ExpireAlert,
        seen: Callable[[str], bool],
        clock: Clock,
        next_stop_margin: timedelta,
    ) -> None:
        self._alerts = alerts
        self._network = network
        self._expire = expire
        self._seen = seen
        self._clock = clock
        self._margin = next_stop_margin

    async def tick(self) -> None:
        now = self._clock.now()
        stop_times: dict[str, list[TripStopTime]] = {}
        for alert in self._alerts.list_all():
            if alert.trip_id not in stop_times:
                stop_times[alert.trip_id] = self._network.trip_stop_times(alert.trip_id)
            next_stop_at = next_stop_scheduled_at(
                stop_times[alert.trip_id], alert.stop_sequence, alert.service_date
            )
            reason = expiry_reason(
                alert, now, next_stop_at, self._seen(alert.alert_id), self._margin
            )
            if reason is not None:
                self._expire(alert, reason)
