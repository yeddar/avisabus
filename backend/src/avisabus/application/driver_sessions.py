"""Use cases of the driver's shift (driver_session design §2, CU-08, CU-09, CU-10).

Privacy (AC-15): the log carries the `session_id` and the departure, never the code, the token,
the coordinates or the address. The token only leaves in `StartedDriverSession`, once, and only
its SHA-256 is stored.
"""

import math
import secrets
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

from avisabus.application.close_driver_session import CloseDriverSession
from avisabus.domain.errors import (
    DepartureTakenError,
    InvalidDepartureError,
    InvalidDriverCodeError,
    InvalidPositionError,
    InvalidSessionError,
    NoActiveFeedError,
    RateLimitedError,
)
from avisabus.domain.models.driver import (
    DriverCode,
    DriverPosition,
    DriverService,
    DriverSession,
    GpsState,
    SessionCloseReason,
    SessionProgress,
    UpcomingStop,
)
from avisabus.domain.models.network import (
    Departure,
    LineDirectionsView,
    ShapePoint,
    TripStopTime,
)
from avisabus.domain.ports.alerts import RateLimiter
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.driver import (
    DriverCodeHasher,
    DriverCodeRepository,
    DriverSessionListener,
    DriverSessionRepository,
    SessionTokenHasher,
)
from avisabus.domain.ports.network import NetworkRepository
from avisabus.domain.services.geometry import project_onto_shape, shape_distances
from avisabus.domain.services.occupancy_simulation import LOCAL_TIMEZONE, service_day_start
from avisabus.domain.services.upcoming_stops import (
    OFF_ROUTE_M,
    project_progress,
    upcoming_stops,
)

DEPARTURES_BEFORE = timedelta(minutes=30)
DEPARTURES_AFTER = timedelta(minutes=60)
TOKEN_BYTES = 32
CODE_LENGTH = 8
POSITION_FUTURE_TOLERANCE = timedelta(seconds=30)
DRIVER_SESSION_STARTED = "driver.session_started"
DRIVER_SERVICE_SELECTED = "driver.service_selected"
DRIVER_LOGIN_FAILED = "driver.login_failed"


class Logger(Protocol):
    def info(self, event: str, **fields: Any) -> Any: ...


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


class LoginLimiter:
    """Failed logins per address (AC-02, design §3): after `max_failures` failures in `block`, the
    address is blocked until `block` after the last one.

    `limiter` admits `max_failures − 1` attempts per `block`, so it rejects exactly the failure
    that completes the count. Only failures call `acquire`; while blocked the code is not checked,
    so no failure can extend the block. Keys are in memory only and never logged (RNF-06).
    """

    def __init__(self, limiter: RateLimiter, block: timedelta) -> None:
        self._limiter = limiter
        self._block = block
        self._blocked_until: dict[str, datetime] = {}

    @property
    def blocked_addresses(self) -> int:
        return len(self._blocked_until)

    def check(self, client_ip: str, now: datetime) -> None:
        """Raises `RateLimitedError` if the address is blocked."""
        self._blocked_until = {
            key: until for key, until in self._blocked_until.items() if until > now
        }
        until = self._blocked_until.get(self._key(client_ip))
        if until is not None:
            raise RateLimitedError(max(1, math.ceil((until - now).total_seconds())))

    def record_failure(self, client_ip: str, now: datetime) -> None:
        key = self._key(client_ip)
        if self._limiter.acquire(key, now) is not None:
            self._blocked_until[key] = now + self._block

    @staticmethod
    def _key(client_ip: str) -> str:
        return f"driver-login:{client_ip}"


@dataclass(frozen=True, slots=True)
class StartDriverSessionCommand:
    code: str = field(repr=False)
    client_ip: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class StartedDriverSession:
    session_id: str
    session_token: str = field(repr=False)
    """Only to return it once; left out of `repr` so that it cannot reach a log by accident."""
    idle_timeout_s: int


class StartDriverSession:
    def __init__(
        self,
        codes: DriverCodeRepository,
        code_hasher: DriverCodeHasher,
        sessions: DriverSessionRepository,
        token_hasher: SessionTokenHasher,
        close: CloseDriverSession,
        limiter: LoginLimiter,
        clock: Clock,
        idle_timeout: timedelta,
        logger: Logger,
    ) -> None:
        self._codes = codes
        self._code_hasher = code_hasher
        self._sessions = sessions
        self._token_hasher = token_hasher
        self._close = close
        self._limiter = limiter
        self._clock = clock
        self._idle_timeout = idle_timeout
        self._log = logger

    async def execute(self, command: StartDriverSessionCommand) -> StartedDriverSession:
        """Raises `RateLimitedError` (AC-02), or `InvalidDriverCodeError` for a code that is
        malformed, unknown or revoked (same error for all)."""
        now = self._clock.now()
        self._limiter.check(command.client_ip, now)
        code = self._active_code(command.code)
        if code is None:
            self._limiter.record_failure(command.client_ip, now)
            self._log.info(DRIVER_LOGIN_FAILED)
            raise InvalidDriverCodeError()
        previous = self._sessions.by_code(code.code_id)
        if previous is not None:
            await self._close.execute(previous.session_id, SessionCloseReason.REPLACED)
        token = secrets.token_urlsafe(TOKEN_BYTES)
        session = DriverSession(
            session_id=str(uuid.uuid4()),
            token_hash=self._token_hasher.hash(token),
            code_id=code.code_id,
            started_at=now,
            service=None,
            position=None,
            progress_m=None,
            off_route=False,
            last_position_at=None,
        )
        self._sessions.add(session)
        self._log.info(DRIVER_SESSION_STARTED, session_id=session.session_id)
        return StartedDriverSession(
            session_id=session.session_id,
            session_token=token,
            idle_timeout_s=int(self._idle_timeout.total_seconds()),
        )

    def _active_code(self, typed: str) -> DriverCode | None:
        digits = typed.replace(" ", "")
        if len(digits) != CODE_LENGTH or not (digits.isascii() and digits.isdigit()):
            return None
        code = self._codes.find_by_hash(self._code_hasher.hash(digits))
        return None if code is None or code.revoked else code


class AuthenticateDriverSession:
    """`current_session` of the endpoints: the open shift of a bearer token (AC-04)."""

    def __init__(self, sessions: DriverSessionRepository, hasher: SessionTokenHasher) -> None:
        self._sessions = sessions
        self._hasher = hasher

    async def execute(self, token: str) -> DriverSession:
        session = self._sessions.by_token_hash(self._hasher.hash(token))
        if session is None:
            raise InvalidSessionError()
        return session


@dataclass(frozen=True, slots=True)
class TripRoute:
    shape: tuple[ShapePoint, ...]
    distances: tuple[float, ...]
    stops: tuple[tuple[UpcomingStop, float], ...]
    """Stops of the trip, in order, with their distance along the shape."""


class TripRoutes:
    """Shape and stop distances of a trip (design §3), cached per feed version, shape and stop
    pattern: trips of a shape may call at different stops (design §7, local decision)."""

    def __init__(self, network: NetworkRepository) -> None:
        self._network = network
        self._version: int | None = None
        self._cache: dict[tuple[str, tuple[tuple[str, int], ...]], TripRoute] = {}

    def of(self, trip_id: str) -> TripRoute | None:
        """`None` if the trip cannot be followed on the active network (it is gone, or it has no
        shape or stops): the shift keeps working without next stops."""
        feed = self._network.active_feed()
        if feed is None:
            return None
        if feed.version_id != self._version:
            self._version = feed.version_id
            self._cache.clear()
        shape_id = self._network.trip_shape_id(trip_id)
        stop_times = self._network.trip_stop_times(trip_id)
        if shape_id is None or not stop_times:
            return None
        key = (shape_id, tuple((st.stop_id, st.stop_sequence) for st in stop_times))
        route = self._cache.get(key)
        if route is None:
            route = self._load(shape_id, stop_times)
            if route is not None:
                self._cache[key] = route
        return route

    def _load(self, shape_id: str, stop_times: Sequence[TripStopTime]) -> TripRoute | None:
        shape = self._network.shape_points(shape_id)
        if not shape:
            return None
        found = [self._network.get_stop(st.stop_id) for st in stop_times]
        stops = [stop for stop in found if stop is not None]
        if len(stops) != len(stop_times):
            return None
        distances = shape_distances(shape)
        feed = [st.shape_dist_traveled for st in stop_times]
        if all(d is not None for d in feed):
            along = [float(d) for d in feed if d is not None]
        else:
            along = project_onto_shape([(s.lat, s.lon) for s in stops], shape, distances)
        return TripRoute(
            shape=tuple(shape),
            distances=tuple(distances),
            stops=tuple(
                (UpcomingStop(stop.stop_id, stop.name, st.stop_sequence, 0.0), d)
                for stop, st, d in zip(stops, stop_times, along, strict=True)
            ),
        )


@dataclass(frozen=True, slots=True)
class DriverSessionState:
    """What `GET /sessions/current` and `PUT …/service` answer (AC-11)."""

    session_id: str
    service: DriverService | None
    progress: SessionProgress


class GetDriverSession:
    def __init__(self, routes: TripRoutes, clock: Clock, gps_stale: timedelta) -> None:
        self._routes = routes
        self._clock = clock
        self._gps_stale = gps_stale

    async def execute(self, session: DriverSession) -> DriverSessionState:
        upcoming: tuple[UpcomingStop, ...] = ()
        finished = False
        if session.service is not None and session.progress_m is not None:
            route = self._routes.of(session.service.trip_id)
            if route is not None:
                upcoming, finished = upcoming_stops(route.stops, session.progress_m)
        return DriverSessionState(
            session_id=session.session_id,
            service=session.service,
            progress=SessionProgress(
                gps=self._gps_state(session),
                off_route=session.off_route,
                finished=finished,
                upcoming=upcoming,
            ),
        )

    def _gps_state(self, session: DriverSession) -> GpsState:
        if session.last_position_at is None:
            return GpsState.WAITING
        if self._clock.now() - session.last_position_at > self._gps_stale:
            return GpsState.STALE
        return GpsState.OK


@dataclass(frozen=True, slots=True)
class SelectDriverServiceCommand:
    session: DriverSession
    service: DriverService


class SelectDriverService:
    def __init__(
        self,
        network: NetworkRepository,
        sessions: DriverSessionRepository,
        listener: DriverSessionListener,
        state: GetDriverSession,
        clock: Clock,
        logger: Logger,
    ) -> None:
        self._network = network
        self._sessions = sessions
        self._listener = listener
        self._state = state
        self._clock = clock
        self._log = logger

    async def execute(self, command: SelectDriverServiceCommand) -> DriverSessionState:
        """Raises `InvalidDepartureError` if AC-06 would not offer it, `DepartureTakenError` if
        another shift holds it (AC-07) and `NoActiveFeedError` without a network."""
        session, service = command.session, command.service
        _require_active_feed(self._network)
        offered = _departures_in_window(
            self._network, service.line, service.direction_id, self._clock.now()
        )
        if not any(
            departure.trip_id == service.trip_id and departure.service_date == service.service_date
            for departure, _ in offered
        ):
            raise InvalidDepartureError()
        holder = self._sessions.by_trip(service.trip_id, service.service_date)
        if holder is not None and holder.session_id != session.session_id:
            raise DepartureTakenError()
        updated = replace(session, service=service, progress_m=None, off_route=False)
        self._sessions.save(updated)
        self._listener.service_selected(updated, session.service)
        self._log.info(
            DRIVER_SERVICE_SELECTED,
            session_id=session.session_id,
            line=service.line,
            direction_id=service.direction_id,
            trip_id=service.trip_id,
        )
        return await self._state.execute(updated)


@dataclass(frozen=True, slots=True)
class UpdateDriverPositionCommand:
    session: DriverSession
    lat: float = field(repr=False)
    lon: float = field(repr=False)
    accuracy_m: float = field(repr=False)
    recorded_at: datetime


class UpdateDriverPosition:
    def __init__(
        self,
        sessions: DriverSessionRepository,
        routes: TripRoutes,
        listener: DriverSessionListener,
        clock: Clock,
    ) -> None:
        self._sessions = sessions
        self._routes = routes
        self._listener = listener
        self._clock = clock

    async def execute(self, command: UpdateDriverPositionCommand) -> None:
        """Keep only the last position (AC-08) and move the progress (AC-09). Raises
        `InvalidPositionError` if it was recorded too far in the future."""
        session = command.session
        now = self._clock.now()
        try:
            recorded_at = command.recorded_at.astimezone(UTC)
        except OverflowError:  # outside the calendar once in UTC (year 1 or 9999 with an offset)
            raise InvalidPositionError() from None
        if recorded_at > now + POSITION_FUTURE_TOLERANCE:
            raise InvalidPositionError()
        if session.position is not None and recorded_at < session.position.recorded_at:
            return
        position = DriverPosition(command.lat, command.lon, command.accuracy_m, recorded_at)
        progress_m, off_route = self._progress(session, position)
        updated = replace(
            session,
            position=position,
            progress_m=progress_m,
            off_route=off_route,
            last_position_at=now,
        )
        self._sessions.save(updated)
        self._listener.position_updated(updated)

    def _progress(
        self, session: DriverSession, position: DriverPosition
    ) -> tuple[float | None, bool]:
        if session.service is None:
            return session.progress_m, session.off_route
        route = self._routes.of(session.service.trip_id)
        if route is None:
            return session.progress_m, session.off_route
        candidate, distance = project_progress(
            route.shape, route.distances, position.lat, position.lon, session.progress_m
        )
        if distance > OFF_ROUTE_M:
            return session.progress_m, True
        if session.progress_m is None:
            return candidate, False
        return max(session.progress_m, candidate), False


class EndDriverSession:
    def __init__(self, close: CloseDriverSession) -> None:
        self._close = close

    async def execute(self, session: DriverSession) -> None:
        await self._close.execute(session.session_id, SessionCloseReason.ENDED)
