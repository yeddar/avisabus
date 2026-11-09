"""Use cases of the stop endpoints, built from the settings (stop_arrivals_api design §2).

`avisabus.main` calls `build_stop_use_cases` at start-up; the integration tests call it too, with
a `FakeClock` and a replayed or fake arrivals source.
"""

import asyncio
import math
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from datetime import timedelta

import structlog
from sqlalchemy import Engine

from avisabus.adapters.inbound.ws.connections import ConnectionRegistry
from avisabus.adapters.inbound.ws.passenger import (
    AlertSnapshotProvider,
    EmptySnapshotProvider,
    PassengerSnapshotProvider,
    PassengerSocket,
)
from avisabus.adapters.outbound.drivers.no_driver_directory import NoDriverDirectory
from avisabus.adapters.outbound.drivers.noop_notifier import NoopDriverViewNotifier
from avisabus.adapters.outbound.drivers.noop_session_listener import NoopDriverSessionListener
from avisabus.adapters.outbound.events.in_memory import InMemoryEventPublisher
from avisabus.adapters.outbound.persistence.sqlite_alerts import SqliteAlertRepository
from avisabus.adapters.outbound.persistence.sqlite_driver_codes import SqliteDriverCodeRepository
from avisabus.adapters.outbound.persistence.sqlite_driver_sessions import (
    SqliteDriverSessionRepository,
)
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.adapters.outbound.rate_limit.in_memory import InMemoryRateLimiter
from avisabus.adapters.outbound.security.hmac_device_hasher import HmacDeviceHasher
from avisabus.adapters.outbound.security.hmac_driver_code_hasher import HmacDriverCodeHasher
from avisabus.adapters.outbound.security.hmac_stop_token import HmacStopTokenSigner
from avisabus.adapters.outbound.security.sha256_session_token_hasher import (
    Sha256SessionTokenHasher,
)
from avisabus.application.cancel_alert import CancelAlert
from avisabus.application.close_driver_session import CloseDriverSession
from avisabus.application.create_alert import CreateAlert
from avisabus.application.direction_overrides import validate_direction_overrides
from avisabus.application.driver_sessions import (
    AuthenticateDriverSession,
    EndDriverSession,
    GetDriverSession,
    ListDepartures,
    ListDriverLines,
    LoginLimiter,
    SelectDriverService,
    StartDriverSession,
    TripRoutes,
    UpdateDriverPosition,
)
from avisabus.application.expire_alert import ExpireAlert
from avisabus.application.expire_alerts import ExpireDueAlerts
from avisabus.application.get_shape import GetShape
from avisabus.application.get_stop import GetStop
from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.application.get_vehicle_position import GetVehiclePosition
from avisabus.application.list_my_alerts import ListMyAlerts
from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from avisabus.application.watch_passages import WatchPassages
from avisabus.config import Settings
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.device import DeviceHasher
from avisabus.domain.ports.driver import DriverSessionListener
from avisabus.domain.ports.events import EventPublisher
from avisabus.domain.ports.occupancy import OccupancySensor
from avisabus.domain.services.direction_resolver import DEFAULT_ALIASES

ARRIVALS_LOGGER = "avisabus.arrivals"
POSITION_LOGGER = "avisabus.position"
WS_LOGGER = "avisabus.ws"
ALERTS_LOGGER = "avisabus.alerts"
BACKGROUND_LOGGER = "avisabus.background"
DRIVER_LOGGER = "avisabus.driver"


@dataclass(frozen=True, slots=True)
class StopUseCases:
    get_stop: GetStop
    get_stop_arrivals: GetStopArrivals
    direction_overrides: Mapping[tuple[str, str], str]
    """Valid overrides, keyed by (line, SAE destination) (AC-20)."""


def build_stop_use_cases(
    settings: Settings,
    engine: Engine,
    clock: Clock,
    arrivals: ArrivalsSource,
    occupancy: OccupancySensor,
    override_entries: Mapping[str, str],
) -> StopUseCases:
    """`override_entries` come from `read_direction_overrides`; they are checked here against
    the active network (`arrivals.override_invalid`)."""
    network = SqliteNetworkRepository(engine)
    signer = HmacStopTokenSigner(settings.stop_token_secret_bytes())
    logger = structlog.get_logger(ARRIVALS_LOGGER)
    overrides = validate_direction_overrides(override_entries, network, logger)
    scheduled = ScheduledArrivalsProvider(
        network,
        window=timedelta(minutes=settings.scheduled_window_min),
        per_direction=settings.scheduled_per_direction,
    )
    return StopUseCases(
        get_stop=GetStop(network, signer),
        get_stop_arrivals=GetStopArrivals(
            network=network,
            signer=signer,
            arrivals=arrivals,
            scheduled=scheduled,
            occupancy=occupancy,
            thresholds=settings.occupancy_thresholds(),
            clock=clock,
            refresh_after_s=math.ceil(settings.sae_cache_ttl_s),
            match_tolerance=timedelta(minutes=settings.trip_match_tolerance_min),
            aliases=DEFAULT_ALIASES,
            direction_overrides=overrides,
            min_score=settings.direction_min_score,
            alert_max_lead=timedelta(minutes=settings.alert_max_lead_min),
            logger=logger,
        ),
        direction_overrides=overrides,
    )


@dataclass(frozen=True, slots=True)
class PositionUseCases:
    """Use cases of the position and shape endpoints (position_estimation design §2)."""

    get_vehicle_position: GetVehiclePosition
    get_shape: GetShape


def build_position_use_cases(stops: StopUseCases, engine: Engine, clock: Clock) -> PositionUseCases:
    """The position reuses the stops' `GetStopArrivals`, so it shares its SAE cache (AC-09)."""
    network = SqliteNetworkRepository(engine)
    return PositionUseCases(
        get_vehicle_position=GetVehiclePosition(
            stops.get_stop_arrivals, network, clock, structlog.get_logger(POSITION_LOGGER)
        ),
        get_shape=GetShape(network),
    )


@dataclass(frozen=True, slots=True)
class Realtime:
    """Real-time events and WebSockets (realtime_events design §2). `create_app` mounts
    `/ws/passenger`, keeps `hasher` for `device_hash_from_header` and runs `registry` in the
    lifespan (`ws.stats`, close with `1001` on stop)."""

    publisher: EventPublisher
    hasher: DeviceHasher
    registry: ConnectionRegistry
    passenger: PassengerSocket


def build_realtime(
    settings: Settings,
    clock: Clock,
    snapshots: PassengerSnapshotProvider | None = None,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> Realtime:
    """`snapshots` defaults to `EmptySnapshotProvider`; the application passes the active alerts
    (`build_alert_snapshots`). The device hash key derives from the stop token secret (no new
    variable)."""
    logger = structlog.get_logger(WS_LOGGER)
    publisher = InMemoryEventPublisher(queue_size=settings.event_queue_size)
    hasher = HmacDeviceHasher(settings.stop_token_secret_bytes())
    registry = ConnectionRegistry(
        max_connections=settings.ws_max_connections,
        clock=clock,
        publisher=publisher,
        logger=logger,
        sleep=sleep,
    )
    passenger = PassengerSocket(
        publisher=publisher,
        hasher=hasher,
        snapshots=snapshots or EmptySnapshotProvider(),
        registry=registry,
        logger=logger,
        hello_timeout_s=settings.ws_hello_timeout_s,
        ping_interval_s=settings.ws_ping_interval_s,
        sleep=sleep,
    )
    return Realtime(publisher=publisher, hasher=hasher, registry=registry, passenger=passenger)


@dataclass(frozen=True, slots=True)
class AlertUseCases:
    """Use cases of the alert endpoints (alert_create and alert_cancel design §2)."""

    create_alert: CreateAlert
    list_my_alerts: ListMyAlerts
    cancel_alert: CancelAlert


def build_alert_use_cases(
    settings: Settings,
    engine: Engine,
    clock: Clock,
    stops: StopUseCases,
    publisher: EventPublisher,
) -> AlertUseCases:
    """The bus is validated with the stops' `GetStopArrivals`, so it shares its SAE cache
    (AC-03); the events (confirmation and `alert.cancelled`) go through the real-time
    publisher. Block 3 has no drivers nor driver views to refresh."""
    window = timedelta(minutes=settings.alert_rate_window_min)
    alerts = SqliteAlertRepository(engine)
    logger = structlog.get_logger(ALERTS_LOGGER)
    return AlertUseCases(
        create_alert=CreateAlert(
            stop_arrivals=stops.get_stop_arrivals,
            network=SqliteNetworkRepository(engine),
            alerts=alerts,
            drivers=NoDriverDirectory(),
            device_limiter=InMemoryRateLimiter(limit=settings.alert_rate_device, window=window),
            ip_limiter=InMemoryRateLimiter(limit=settings.alert_rate_ip, window=window),
            events=publisher,
            clock=clock,
            max_age=timedelta(minutes=settings.alert_max_age_min),
            logger=logger,
        ),
        list_my_alerts=ListMyAlerts(alerts),
        cancel_alert=CancelAlert(
            alerts=alerts, events=publisher, drivers=NoopDriverViewNotifier(), logger=logger
        ),
    )


def build_alert_snapshots(engine: Engine) -> AlertSnapshotProvider:
    """`alerts.snapshot` of `/ws/passenger` with the active alerts of the device (AC-11). Built
    before `build_realtime`, which needs it, while `build_alert_use_cases` needs its publisher."""
    return AlertSnapshotProvider(ListMyAlerts(SqliteAlertRepository(engine)))


@dataclass(frozen=True, slots=True)
class AlertExpiry:
    """Cycles of the alert expiry tasks (alert_expiry design §2); `avisabus.main` runs them
    periodically in its lifespan (`background.alert_tasks`)."""

    watch_passages: WatchPassages
    expire_due_alerts: ExpireDueAlerts
    watch_interval: timedelta
    expiry_interval: timedelta


def build_alert_expiry(
    settings: Settings,
    engine: Engine,
    clock: Clock,
    stops: StopUseCases,
    publisher: EventPublisher,
) -> AlertExpiry:
    """The watcher reads the stops through the stops' `GetStopArrivals`, so it shares its SAE
    cache (AC-04); the ticker reads what the watcher remembers of the last observation of each
    alert (`seen_in_last_observation`). `alert.expired` goes through the real-time publisher.
    Block 3 has no driver views to refresh."""
    alerts = SqliteAlertRepository(engine)
    network = SqliteNetworkRepository(engine)
    logger = structlog.get_logger(ALERTS_LOGGER)
    expire = ExpireAlert(
        alerts=alerts, events=publisher, drivers=NoopDriverViewNotifier(), logger=logger
    )
    watch = WatchPassages(
        alerts=alerts,
        stop_arrivals=stops.get_stop_arrivals,
        network=network,
        expire=expire,
        clock=clock,
        logger=logger,
        passage_window=timedelta(minutes=settings.passage_window_min),
    )
    return AlertExpiry(
        watch_passages=watch,
        expire_due_alerts=ExpireDueAlerts(
            alerts=alerts,
            network=network,
            expire=expire,
            seen=watch.seen_in_last_observation,
            clock=clock,
            next_stop_margin=timedelta(minutes=settings.next_stop_margin_min),
        ),
        watch_interval=timedelta(seconds=settings.passage_watch_interval_s),
        expiry_interval=timedelta(seconds=settings.alert_expiry_interval_s),
    )


@dataclass(frozen=True, slots=True)
class DriverUseCases:
    """Use cases of the driver endpoints (driver_session design §2)."""

    start_session: StartDriverSession
    authenticate: AuthenticateDriverSession
    list_lines: ListDriverLines
    list_departures: ListDepartures
    select_service: SelectDriverService
    update_position: UpdateDriverPosition
    get_session: GetDriverSession
    end_session: EndDriverSession


def build_driver_use_cases(
    settings: Settings,
    engine: Engine,
    clock: Clock,
    listener: DriverSessionListener | None = None,
) -> DriverUseCases:
    """`listener` defaults to `NoopDriverSessionListener`; `driver_demand` passes its own. The
    code hash key derives from the stop token secret, as in the `driver-codes` commands."""
    sessions = SqliteDriverSessionRepository(engine)
    network = SqliteNetworkRepository(engine)
    logger = structlog.get_logger(DRIVER_LOGGER)
    session_listener = listener or NoopDriverSessionListener()
    token_hasher = Sha256SessionTokenHasher()
    routes = TripRoutes(network)
    close = CloseDriverSession(sessions, session_listener, clock, logger)
    block = timedelta(minutes=settings.driver_login_block_min)
    get_session = GetDriverSession(routes, clock, timedelta(seconds=settings.driver_gps_stale_s))
    return DriverUseCases(
        start_session=StartDriverSession(
            codes=SqliteDriverCodeRepository(engine),
            code_hasher=HmacDriverCodeHasher(settings.stop_token_secret_bytes()),
            sessions=sessions,
            token_hasher=token_hasher,
            close=close,
            limiter=LoginLimiter(
                InMemoryRateLimiter(limit=settings.driver_login_max_failures - 1, window=block),
                block=block,
            ),
            clock=clock,
            idle_timeout=timedelta(minutes=settings.driver_idle_timeout_min),
            logger=logger,
        ),
        authenticate=AuthenticateDriverSession(sessions, token_hasher),
        list_lines=ListDriverLines(network),
        list_departures=ListDepartures(network, sessions, clock),
        select_service=SelectDriverService(
            network, sessions, session_listener, get_session, clock, logger
        ),
        update_position=UpdateDriverPosition(sessions, routes, session_listener, clock),
        get_session=get_session,
        end_session=EndDriverSession(close),
    )
