"""What `driver_demand` does when a shift or a request changes (design §1, §3).

`DemandSessionListener` is the `DriverSessionListener` of `driver_session`, and
`DemandViewNotifier` the `DriverViewNotifier` of `alert_cancel` and `alert_expiry`.
"""

from avisabus.application.deliver_alerts import DeliverPendingAlerts, UndeliverSessionAlerts
from avisabus.application.demand_views import DemandViews, driver_channel, session_closed_event
from avisabus.application.driver_sessions import TripRoutes
from avisabus.domain.models.driver import (
    DriverService,
    DriverSession,
    GpsState,
    SessionCloseReason,
    UpcomingStop,
)
from avisabus.domain.models.driver_view import DriverView
from avisabus.domain.ports.events import EventPublisher
from avisabus.domain.services.upcoming_stops import upcoming_stops


class DemandViewNotifier:
    def __init__(self, views: DemandViews) -> None:
        self._views = views

    def alert_removed(self, session_id: str) -> None:
        self._views.touch(session_id)


class DemandSessionListener:
    def __init__(
        self,
        views: DemandViews,
        deliver: DeliverPendingAlerts,
        undeliver: UndeliverSessionAlerts,
        routes: TripRoutes,
        events: EventPublisher,
    ) -> None:
        self._views = views
        self._deliver = deliver
        self._undeliver = undeliver
        self._routes = routes
        self._events = events

    def service_selected(self, session: DriverSession, previous: DriverService | None) -> None:
        self._deliver(session, previous)
        self._views.touch(session.session_id)

    def position_updated(self, session: DriverSession) -> None:
        """Only when something the driver sees changes (AC-09). The distances change with every
        position, so they are not compared: the periodic refresh updates them."""
        last = self._views.last_view(session.session_id)
        if last is None or self._differs(last, session):
            self._views.touch(session.session_id)

    def session_closed(self, session_id: str, reason: SessionCloseReason) -> None:
        self._undeliver(session_id)
        self._views.forget(session_id)
        self._events.publish(driver_channel(session_id), session_closed_event(reason))

    def _differs(self, last: DriverView, session: DriverSession) -> bool:
        upcoming, finished = self._progress(session)
        return (
            last.gps is not GpsState.OK  # a position has just been accepted
            or last.off_route != session.off_route
            or last.finished != finished
            or [(stop.stop_id, stop.stop_sequence) for stop in last.stops]
            != [(stop.stop_id, stop.stop_sequence) for stop in upcoming]
        )

    def _progress(self, session: DriverSession) -> tuple[tuple[UpcomingStop, ...], bool]:
        if session.service is None or session.progress_m is None:
            return (), False
        route = self._routes.of(session.service.trip_id)
        if route is None:
            return (), False
        return upcoming_stops(route.stops, session.progress_m)
