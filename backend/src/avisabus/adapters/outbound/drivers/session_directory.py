"""`DriverDirectory` over the open shifts (driver_demand, ADR-016, ADR-018): a bus is driven by the
open shift that holds its trip on that service day."""

from datetime import date

from avisabus.domain.ports.alerts import DriverRef
from avisabus.domain.ports.driver import DriverSessionRepository


class SessionDriverDirectory:
    def __init__(self, sessions: DriverSessionRepository) -> None:
        self._sessions = sessions

    def find_driver(
        self, line: str, direction_id: int, trip_id: str, service_date: date
    ) -> DriverRef | None:
        session = self._sessions.by_trip(trip_id, service_date)
        return None if session is None else DriverRef(session.session_id)
