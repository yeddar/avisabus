"""Builds what a driver sees (driver_demand design §1, RF-27, RF-29, CU-09).

Every call builds a complete view (ADR-009). The view is never logged (AC-12).
"""

from datetime import datetime, timedelta

from avisabus.application.driver_sessions import GetDriverSession
from avisabus.domain.models.driver import DriverService, DriverSession
from avisabus.domain.models.driver_view import DriverServiceView, DriverView
from avisabus.domain.models.occupancy import OccupancyThresholds, VehicleRef
from avisabus.domain.ports.alerts import AlertRepository
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.driver import DriverSessionRepository
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.ports.occupancy import OccupancySensor
from avisabus.domain.services.demand import capacity_flags, stop_demand
from avisabus.domain.services.occupancy_classifier import classify_occupancy
from avisabus.domain.services.occupancy_simulation import service_day_start


class BuildDriverView:
    def __init__(
        self,
        sessions: DriverSessionRepository,
        alerts: AlertRepository,
        network: NetworkRepository,
        state: GetDriverSession,
        occupancy: OccupancySensor,
        thresholds: OccupancyThresholds,
        clock: Clock,
    ) -> None:
        self._sessions = sessions
        self._alerts = alerts
        self._network = network
        self._state = state
        self._occupancy = occupancy
        self._thresholds = thresholds
        self._clock = clock

    def open_session_ids(self) -> list[str]:
        return [session.session_id for session in self._sessions.list_all()]

    async def for_session_id(self, session_id: str) -> DriverView | None:
        """The view of an open shift; `None` if it is no longer open. The port has no search by
        id: there are few open shifts (as in `CloseDriverSession`)."""
        session = next((s for s in self._sessions.list_all() if s.session_id == session_id), None)
        return None if session is None else await self.execute(session)

    async def execute(self, session: DriverSession) -> DriverView:
        now = self._clock.now()
        progress = (await self._state.execute(session)).progress
        service = None if session.service is None else self._service_view(session.service)
        stops = (
            ()
            if service is None
            else stop_demand(progress.upcoming, self._alerts.list_by_session(session.session_id))
        )
        free_places, free_seats = (
            (None, None) if service is None else await self._free_places(service, now)
        )
        capacity_alert, seat_alert = capacity_flags(stops, free_places, free_seats)
        return DriverView(
            generated_at=now,
            service=service,
            gps=progress.gps,
            off_route=progress.off_route,
            finished=progress.finished,
            stops=stops,
            total_waiting=sum(stop.waiting for stop in stops),
            free_places=free_places,
            free_seats=free_seats,
            capacity_alert=capacity_alert,
            seat_alert=seat_alert,
        )

    def _service_view(self, service: DriverService) -> DriverServiceView | None:
        """`None` if the departure is no longer in the active network (the feed changed during
        the shift): it is shown as a shift without a departure, so that the driver can choose
        another one."""
        stop_times = self._network.trip_stop_times(service.trip_id)
        line = self._network.get_line(service.line)
        if not stop_times or line is None:
            return None
        departure_s = min(stop_times, key=lambda stop_time: stop_time.stop_sequence).departure_s
        departures = self._network.departures(
            service.line, service.direction_id, service.service_date, departure_s, departure_s
        )
        departure = next((d for d in departures if d.trip_id == service.trip_id), None)
        if departure is None:
            return None
        return DriverServiceView(
            line=service.line,
            direction_id=service.direction_id,
            headsign=departure.headsign,
            trip_id=service.trip_id,
            service_date=service.service_date,
            departure_at=service_day_start(service.service_date) + timedelta(seconds=departure_s),
            color=line.color,
            text_color=line.text_color,
        )

    async def _free_places(
        self, service: DriverServiceView, now: datetime
    ) -> tuple[int | None, int | None]:
        reading = await self._occupancy.read(VehicleRef(service.trip_id, service.service_date), now)
        if reading is None:
            return None, None
        status = classify_occupancy(reading, self._thresholds)
        return status.free_places, status.free_seats
