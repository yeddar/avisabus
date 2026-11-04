"""Use case: a passenger requests a stop to a chosen bus (alert_create design §3, CU-03).

Order (design §3): rate limits → active alert of the device at that stop and line (`200`, no
arrivals asked) → the stop's arrivals through `GetStopArrivals` (same SAE cache) → the requested
bus among them with `can_alert` → its stop occurrence and delay → driver → store → event.

Privacy (RNF-06, AC-13): the logs never carry the device hash, the IP address nor the needs.
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Protocol

from avisabus.application.alert_events import ALERT_DELIVERED, ALERT_REGISTERED, alert_event
from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.domain.errors import BusNotRequestableError, RateLimitedError, StopNotFoundError
from avisabus.domain.models.alert import (
    Alert,
    AlertStatus,
    AlertTracking,
    Need,
    canonical_needs,
)
from avisabus.domain.models.stop_arrivals import ArrivalSource, ArrivalView, StopArrivals
from avisabus.domain.ports.alerts import AlertRepository, DriverDirectory, RateLimiter
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.events import EventPublisher, device_channel
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.occupancy_simulation import service_day_start


class Logger(Protocol):
    def debug(self, event: str, **fields: Any) -> Any: ...

    def info(self, event: str, **fields: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class CreateAlertCommand:
    device_hash: str
    client_ip: str
    stop_id: str
    token: str
    line: str
    direction_id: int
    trip_id: str
    service_date: date
    needs: tuple[Need, ...]


@dataclass(frozen=True, slots=True)
class CreateAlertResult:
    alert: Alert
    created: bool
    """False: the device already had an active alert at that stop and line (`200`, AC-07)."""


@dataclass(frozen=True, slots=True)
class _StopOccurrence:
    stop_sequence: int
    delay_s: int


class CreateAlert:
    def __init__(
        self,
        stop_arrivals: GetStopArrivals,
        network: NetworkRepository,
        alerts: AlertRepository,
        drivers: DriverDirectory,
        device_limiter: RateLimiter,
        ip_limiter: RateLimiter,
        events: EventPublisher,
        clock: Clock,
        max_age: timedelta,
        logger: Logger,
    ) -> None:
        self._stop_arrivals = stop_arrivals
        self._network = network
        self._alerts = alerts
        self._drivers = drivers
        self._device_limiter = device_limiter
        self._ip_limiter = ip_limiter
        self._events = events
        self._clock = clock
        self._max_age = max_age
        self._log = logger

    async def execute(self, command: CreateAlertCommand) -> CreateAlertResult:
        """Raises `RateLimitedError` (AC-08), `StopNotFoundError` (AC-04), `NoActiveFeedError` and
        `BusNotRequestableError` (AC-03); none of them stores anything nor publishes events."""
        now = self._clock.now()
        limits = self._acquire(command, now)
        if limits is not None:
            self._log.info("alert.rejected", reason="rate_limited", stop_id=command.stop_id)
            raise RateLimitedError(limits)

        existing = self._alerts.find_active(command.device_hash, command.stop_id, command.line)
        if existing is not None:
            return self._duplicate(command, existing, now)

        arrivals = await self._stop_arrivals.execute(command.stop_id, command.token)
        arrival = _requested_arrival(arrivals, command)
        occurrence = None if arrival is None else self._occurrence(command, arrival)
        if arrival is None or occurrence is None:
            self._log.info("alert.rejected", reason="bus_not_requestable", stop_id=command.stop_id)
            raise BusNotRequestableError()
        stop = self._network.get_stop(command.stop_id)
        if stop is None:  # the active feed changed in between
            raise StopNotFoundError(command.stop_id)

        driver = self._drivers.find_driver(
            command.line, command.direction_id, command.trip_id, command.service_date
        )
        alert = Alert(
            alert_id=str(uuid.uuid4()),
            device_hash=command.device_hash,
            stop_id=command.stop_id,
            stop_name=stop.name,
            line=command.line,
            direction_id=command.direction_id,
            destination=arrival.destination,
            trip_id=command.trip_id,
            service_date=command.service_date,
            stop_sequence=occurrence.stop_sequence,
            needs=canonical_needs(command.needs),
            status=AlertStatus.PENDING_DRIVER if driver is None else AlertStatus.DELIVERED,
            delivered_to=None if driver is None else driver.session_id,
            created_at=now,
            expires_at=now + self._max_age,
            tracking=AlertTracking(
                # The trip appears in this observation when it comes from the SAE.
                last_seen_at=arrivals.generated_at
                if arrivals.source is ArrivalSource.REALTIME
                else None,
                last_arrival_at=arrival.arrival_at,
                last_delay_s=occurrence.delay_s,
            ),
        )
        stored = self._alerts.add(alert)
        if stored.alert_id != alert.alert_id:  # a concurrent request stored first (AC-07)
            return self._duplicate(command, stored, now)

        event_type = ALERT_REGISTERED if driver is None else ALERT_DELIVERED
        self._events.publish(device_channel(alert.device_hash), alert_event(event_type, alert))
        self._log.info(
            "alert.created",
            alert_id=alert.alert_id,
            stop_id=alert.stop_id,
            line=alert.line,
            direction_id=alert.direction_id,
            status=alert.status.value,
        )
        return CreateAlertResult(alert=alert, created=True)

    def _acquire(self, command: CreateAlertCommand, now: datetime) -> int | None:
        """Both limiters see the attempt; `Retry-After` is the larger wait (AC-08)."""
        waits = [
            wait
            for wait in (
                self._device_limiter.acquire(_device_key(command), now),
                self._ip_limiter.acquire(_ip_key(command), now),
            )
            if wait is not None
        ]
        return max(waits) if waits else None

    def _duplicate(
        self, command: CreateAlertCommand, existing: Alert, now: datetime
    ) -> CreateAlertResult:
        """A `200` does not count towards the limits and emits no events (AC-07, AC-08)."""
        self._device_limiter.release(_device_key(command), now)
        self._ip_limiter.release(_ip_key(command), now)
        self._log.debug("alert.duplicate", stop_id=command.stop_id, line=command.line)
        return CreateAlertResult(alert=existing, created=False)

    def _occurrence(
        self, command: CreateAlertCommand, arrival: ArrivalView
    ) -> _StopOccurrence | None:
        """Occurrence of the stop in the trip whose scheduled time is closest to the arrival
        (same rule as position_estimation AC-07) and the delay there; `None` if the trip no
        longer calls at the stop (the active feed changed in between)."""
        day_start = service_day_start(command.service_date)
        stop_times = sorted(
            (
                stop_time
                for stop_time in self._network.trip_stop_times(command.trip_id)
                if stop_time.stop_id == command.stop_id
            ),
            key=lambda stop_time: stop_time.stop_sequence,
        )
        if not stop_times:
            return None
        closest = min(
            stop_times,
            key=lambda stop_time: abs(
                day_start + timedelta(seconds=stop_time.arrival_s) - arrival.arrival_at
            ),
        )
        scheduled = day_start + timedelta(seconds=closest.arrival_s)
        return _StopOccurrence(
            stop_sequence=closest.stop_sequence,
            delay_s=round((arrival.arrival_at - scheduled).total_seconds()),
        )


def _requested_arrival(arrivals: StopArrivals, command: CreateAlertCommand) -> ArrivalView | None:
    """The arrival of that bus (line, direction, trip and service day) if it can be requested."""
    return next(
        (
            arrival
            for arrival in arrivals.arrivals
            if arrival.can_alert
            and arrival.line == command.line
            and arrival.direction_id == command.direction_id
            and arrival.vehicle is not None
            and arrival.vehicle.trip_id == command.trip_id
            and arrival.vehicle.service_date == command.service_date
        ),
        None,
    )


def _device_key(command: CreateAlertCommand) -> str:
    return f"device:{command.device_hash}"


def _ip_key(command: CreateAlertCommand) -> str:
    return f"ip:{command.client_ip}"
