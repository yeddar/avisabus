"""Use cases of the driver's shift (driver_session design §2, CU-08, CU-09, CU-10)."""

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from avisabus.domain.errors import NoActiveFeedError
from avisabus.domain.models.driver import DriverSession
from avisabus.domain.models.network import Departure, LineDirectionsView
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.driver import DriverSessionRepository
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.occupancy_simulation import LOCAL_TIMEZONE, service_day_start

DEPARTURES_BEFORE = timedelta(minutes=30)
DEPARTURES_AFTER = timedelta(minutes=60)


def _require_active_feed(network: NetworkRepository) -> None:
    if network.active_feed() is None:
        raise NoActiveFeedError()


def _departures_in_window(
    network: NetworkRepository, line: str, direction_id: int, now: datetime
) -> list[tuple[Departure, datetime]]:
    """Departures around `now` of today and of the previous service day (times >= 24:00), each
    with its instant, ordered by time and then trip."""
    today = now.astimezone(LOCAL_TIMEZONE).date()
    found: list[tuple[Departure, datetime]] = []
    for service_date in (today, today - timedelta(days=1)):
        start = service_day_start(service_date)
        low = math.ceil((now - DEPARTURES_BEFORE - start).total_seconds())
        high = math.floor((now + DEPARTURES_AFTER - start).total_seconds())
        for departure in network.departures(line, direction_id, service_date, low, high):
            found.append((departure, start + timedelta(seconds=departure.departure_s)))
    found.sort(key=lambda item: (item[1], item[0].trip_id))
    return found


@dataclass(frozen=True, slots=True)
class ListDeparturesCommand:
    session: DriverSession
    line: str
    direction_id: int


@dataclass(frozen=True, slots=True)
class DepartureOption:
    trip_id: str
    service_date: date
    departure_at: datetime
    first_stop_name: str
    headsign: str
    taken: bool
    """Another open shift already holds it."""


class ListDriverLines:
    def __init__(self, network: NetworkRepository) -> None:
        self._network = network

    async def execute(self) -> list[LineDirectionsView]:
        _require_active_feed(self._network)
        return self._network.list_lines()


class ListDepartures:
    def __init__(
        self, network: NetworkRepository, sessions: DriverSessionRepository, clock: Clock
    ) -> None:
        self._network = network
        self._sessions = sessions
        self._clock = clock

    async def execute(self, command: ListDeparturesCommand) -> list[DepartureOption]:
        _require_active_feed(self._network)
        held = {
            (session.service.trip_id, session.service.service_date)
            for session in self._sessions.list_all()
            if session.service is not None and session.session_id != command.session.session_id
        }
        window = _departures_in_window(
            self._network, command.line, command.direction_id, self._clock.now()
        )
        return [
            DepartureOption(
                trip_id=departure.trip_id,
                service_date=departure.service_date,
                departure_at=departure_at,
                first_stop_name=departure.first_stop_name,
                headsign=departure.headsign,
                taken=(departure.trip_id, departure.service_date) in held,
            )
            for departure, departure_at in window
        ]
