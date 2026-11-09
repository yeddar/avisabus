"""`DriverSessionListener` of `driver_session`: nobody listens yet. `driver_demand` replaces it."""

from avisabus.domain.models.driver import DriverService, DriverSession, SessionCloseReason


class NoopDriverSessionListener:
    def service_selected(self, session: DriverSession, previous: DriverService | None) -> None:
        return None

    def position_updated(self, session: DriverSession) -> None:
        return None

    def session_closed(self, session_id: str, reason: SessionCloseReason) -> None:
        return None
