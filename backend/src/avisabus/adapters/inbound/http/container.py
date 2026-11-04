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
from avisabus.adapters.outbound.events.in_memory import InMemoryEventPublisher
from avisabus.adapters.outbound.persistence.sqlite_alerts import SqliteAlertRepository
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.adapters.outbound.rate_limit.in_memory import InMemoryRateLimiter
from avisabus.adapters.outbound.security.hmac_device_hasher import HmacDeviceHasher
from avisabus.adapters.outbound.security.hmac_stop_token import HmacStopTokenSigner
from avisabus.application.cancel_alert import CancelAlert
from avisabus.application.create_alert import CreateAlert
from avisabus.application.direction_overrides import validate_direction_overrides
from avisabus.application.get_shape import GetShape
from avisabus.application.get_stop import GetStop
from avisabus.application.get_stop_arrivals import GetStopArrivals
from avisabus.application.get_vehicle_position import GetVehiclePosition
from avisabus.application.list_my_alerts import ListMyAlerts
from avisabus.application.scheduled_arrivals import ScheduledArrivalsProvider
from avisabus.config import Settings
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.device import DeviceHasher
from avisabus.domain.ports.events import EventPublisher
from avisabus.domain.ports.occupancy import OccupancySensor
from avisabus.domain.services.direction_resolver import DEFAULT_ALIASES

ARRIVALS_LOGGER = "avisabus.arrivals"
POSITION_LOGGER = "avisabus.position"
WS_LOGGER = "avisabus.ws"
ALERTS_LOGGER = "avisabus.alerts"


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
