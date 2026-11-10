"""Publication of the driver views (driver_demand design §1, §3, RF-28, ADR-009).

`touch` asks for a new view of a shift. Each shift has at most one worker: it waits until a second
has passed since its last view and then builds and publishes one, so that every touch in between
ends up in the same view (AC-09). `refresh_all` is the periodic pass that notices what nothing
touches: a GPS that went stale and the occupancy.

The views are never logged, and a failure only logs its type (AC-12, H-01).
"""

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from avisabus.application.build_driver_view import BuildDriverView
from avisabus.domain.models.driver import SessionCloseReason
from avisabus.domain.models.driver_view import DriverServiceView, DriverView, StopDemand
from avisabus.domain.models.events import Event
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.events import EventPublisher

DRIVER_VIEW = "driver.view"
SESSION_CLOSED = "session.closed"
UNHANDLED_EXCEPTION = "unhandled_exception"
DEMAND_VIEW_PUBLISHER = "demand.view_publisher"

Sleep = Callable[[float], Awaitable[None]]
_COMPARED_AT = datetime(1970, 1, 1, tzinfo=UTC)


class Logger(Protocol):
    def error(self, event: str, **fields: Any) -> Any: ...


def driver_channel(session_id: str) -> str:
    """Channel of the events of one shift."""
    return f"driver:{session_id}"


def session_closed_event(reason: SessionCloseReason) -> Event:
    return Event(SESSION_CLOSED, {"reason": reason.value})


def driver_view_event(view: DriverView) -> Event:
    return Event(DRIVER_VIEW, driver_view_payload(view))


def driver_view_payload(view: DriverView) -> dict[str, object]:
    """The view as `/ws/driver` sends it (design §3). Only aggregated needs per stop (AC-05)."""
    return {
        "generated_at": _utc_text(view.generated_at),
        "service": None if view.service is None else _service_payload(view.service),
        "gps": view.gps.value,
        "off_route": view.off_route,
        "finished": view.finished,
        "stops": [_stop_payload(stop) for stop in view.stops],
        "total_waiting": view.total_waiting,
        "free_places": view.free_places,
        "free_seats": view.free_seats,
        "capacity_alert": view.capacity_alert,
        "seat_alert": view.seat_alert,
    }


def _service_payload(service: DriverServiceView) -> dict[str, object]:
    return {
        "line": service.line,
        "direction_id": service.direction_id,
        "headsign": service.headsign,
        "trip_id": service.trip_id,
        "service_date": service.service_date.isoformat(),
        "departure_at": _utc_text(service.departure_at),
        "color": service.color,
        "text_color": service.text_color,
    }


def _stop_payload(stop: StopDemand) -> dict[str, object]:
    return {
        "stop_id": stop.stop_id,
        "name": stop.name,
        "stop_sequence": stop.stop_sequence,
        "distance_m": stop.distance_m,
        "waiting": stop.waiting,
        "needs": {
            "RAMP": stop.needs.RAMP,
            "EXTRA_TIME": stop.needs.EXTRA_TIME,
            "SEAT": stop.needs.SEAT,
            "VISUAL": stop.needs.VISUAL,
        },
        "alert_ids": list(stop.alert_ids),
    }


def _utc_text(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


class DemandViews:
    def __init__(
        self,
        build: BuildDriverView,
        events: EventPublisher,
        clock: Clock,
        min_interval: timedelta = timedelta(seconds=1),
        *,
        logger: Logger,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._build = build
        self._events = events
        self._clock = clock
        self._min_interval = min_interval
        self._log = logger
        self._sleep = sleep
        self._workers: dict[str, asyncio.Task[None]] = {}
        self._dirty: set[str] = set()
        self._published_at: dict[str, datetime] = {}
        self._last: dict[str, DriverView] = {}

    def touch(self, session_id: str) -> None:
        """Schedule a publication. Something that changes while a view is being built is marked
        again, so it reaches the next view instead of being lost."""
        self._dirty.add(session_id)
        if session_id not in self._workers:
            self._workers[session_id] = asyncio.create_task(
                self._run(session_id), name=DEMAND_VIEW_PUBLISHER
            )

    def last_view(self, session_id: str) -> DriverView | None:
        """What the driver saw last, if anything was published."""
        return self._last.get(session_id)

    def forget(self, session_id: str) -> None:
        """The shift has closed: no more views, and nothing of it is kept."""
        self._dirty.discard(session_id)
        self._published_at.pop(session_id, None)
        self._last.pop(session_id, None)
        worker = self._workers.pop(session_id, None)
        if worker is not None:
            worker.cancel()

    async def refresh_all(self) -> None:
        """Only for shifts somebody is watching. A view that changes goes through `touch`, so it
        keeps the limit of one per second; one shift failing does not stop the others."""
        for session_id in self._build.open_session_ids():
            if self._events.subscriber_count(driver_channel(session_id)) == 0:
                continue
            try:
                view = await self._build.for_session_id(session_id)
            except Exception as error:  # the other shifts must be refreshed anyway
                self._log_failure(error)
                continue
            if view is not None and self._has_changed(session_id, view):
                self.touch(session_id)

    async def aclose(self) -> None:
        """Cancel what is pending and wait for it (the application stops)."""
        workers = list(self._workers.values())
        self._workers.clear()
        self._dirty.clear()
        for worker in workers:
            worker.cancel()
        for worker in workers:
            with suppress(asyncio.CancelledError):
                await worker

    def _has_changed(self, session_id: str, view: DriverView) -> bool:
        last = self._last.get(session_id)
        return last is None or _comparable(last) != _comparable(view)

    async def _run(self, session_id: str) -> None:
        current = asyncio.current_task()
        try:
            while session_id in self._dirty:
                wait = self._remaining(session_id)
                if wait > 0:
                    await self._sleep(wait)
                self._dirty.discard(session_id)
                try:
                    await self._publish(session_id)
                except Exception as error:  # the next touch must work
                    self._log_failure(error)
        finally:
            if self._workers.get(session_id) is current:
                del self._workers[session_id]

    def _remaining(self, session_id: str) -> float:
        published_at = self._published_at.get(session_id)
        if published_at is None:
            return 0.0
        elapsed = self._clock.now() - published_at
        return min(self._min_interval, self._min_interval - elapsed).total_seconds()

    async def _publish(self, session_id: str) -> None:
        view = await self._build.for_session_id(session_id)
        if view is None:
            return
        self._last[session_id] = view
        self._published_at[session_id] = self._clock.now()
        self._events.publish(driver_channel(session_id), driver_view_event(view))

    def _log_failure(self, error: Exception) -> None:
        self._log.error(
            UNHANDLED_EXCEPTION, error_type=type(error).__name__, task=DEMAND_VIEW_PUBLISHER
        )


def _comparable(view: DriverView) -> DriverView:
    """The view without what changes on its own at every build."""
    return replace(view, generated_at=_COMPARED_AT)
