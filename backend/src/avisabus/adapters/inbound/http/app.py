"""FastAPI application factory."""

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware

import avisabus
from avisabus.adapters.inbound.http.access_log import mask_driver_addresses
from avisabus.adapters.inbound.http.container import (
    AlertUseCases,
    DriverUseCases,
    PositionUseCases,
    Realtime,
    StopUseCases,
)
from avisabus.adapters.inbound.http.errors import register_error_handlers
from avisabus.adapters.inbound.http.no_store import NoStoreMiddleware
from avisabus.adapters.inbound.http.routes import alerts as alerts_routes
from avisabus.adapters.inbound.http.routes import driver as driver_routes
from avisabus.adapters.inbound.http.routes import health
from avisabus.adapters.inbound.http.routes import position as position_routes
from avisabus.adapters.inbound.http.routes import shapes as shapes_routes
from avisabus.adapters.inbound.http.routes import stops as stops_routes
from avisabus.adapters.inbound.ws import passenger as passenger_socket
from avisabus.adapters.inbound.ws.connections import ConnectionRegistry
from avisabus.config import Settings

API_PREFIX = "/api/v1"
GZIP_MINIMUM_SIZE = 1000
"""Responses of more than ~1 KB are compressed when the client accepts gzip (position_estimation
AC-16)."""


Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    settings: Settings,
    lifespan: Lifespan | None = None,
    stops: StopUseCases | None = None,
    positions: PositionUseCases | None = None,
    realtime: Realtime | None = None,
    alerts: AlertUseCases | None = None,
    drivers: DriverUseCases | None = None,
    *,
    schema_only: bool = False,
) -> FastAPI:
    """`lifespan` starts and stops the background work wired in `avisabus.main`; `stops` adds
    the stop endpoints (stop_arrivals_api), which need the network and the arrivals source;
    `positions` adds the position and shape endpoints (position_estimation); `realtime` adds
    `/ws/passenger` (without the API prefix) and runs its connection registry inside the
    lifespan, so open sockets are closed with `1001` when the application stops
    (realtime_events); `alerts` adds the alert endpoints (alert_create), which need `realtime`
    for the device header and the events, and answers them with `Cache-Control: no-store`;
    `drivers` adds the driver endpoints (driver_session), also with `no-store`.

    With `schema_only`, every router is registered without its dependencies, so the app can only
    describe itself (`openapi_document`); its endpoints must not be called."""
    if realtime is not None:
        lifespan = _with_connections(lifespan, realtime.registry)
    app = FastAPI(title="AvisaBus", version=avisabus.__version__, lifespan=lifespan)
    app.state.settings = settings
    app.add_middleware(GZipMiddleware, minimum_size=GZIP_MINIMUM_SIZE)
    if alerts is not None:
        app.add_middleware(NoStoreMiddleware, path=f"{API_PREFIX}/alerts")
    if drivers is not None:
        app.add_middleware(NoStoreMiddleware, path=f"{API_PREFIX}/driver")
        mask_driver_addresses(f"{API_PREFIX}/driver")
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    if stops is not None:
        app.state.stop_use_cases = stops
    if stops is not None or schema_only:
        app.include_router(stops_routes.router, prefix=API_PREFIX)
    if positions is not None:
        app.state.position_use_cases = positions
    if positions is not None or schema_only:
        app.include_router(position_routes.router, prefix=API_PREFIX)
        app.include_router(shapes_routes.router, prefix=API_PREFIX)
    if realtime is not None:
        app.state.device_hasher = realtime.hasher
        app.state.passenger_socket = realtime.passenger
        app.include_router(passenger_socket.router)  # no /api/v1 (docs/architecture.md §7)
    if alerts is not None:
        app.state.alert_use_cases = alerts
    if alerts is not None or schema_only:
        app.include_router(alerts_routes.router, prefix=API_PREFIX)
    if drivers is not None:
        app.state.driver_use_cases = drivers
    if drivers is not None or schema_only:
        app.include_router(driver_routes.router, prefix=API_PREFIX)
    return app


def _with_connections(lifespan: Lifespan | None, registry: ConnectionRegistry) -> Lifespan:
    """The registry runs inside the given lifespan: its sockets close first on stop."""

    @asynccontextmanager
    async def combined(app: FastAPI) -> AsyncIterator[None]:
        if lifespan is None:
            async with registry.running():
                yield
            return
        async with lifespan(app), registry.running():
            yield

    return combined


def openapi_document() -> dict[str, Any]:
    """OpenAPI document of the whole HTTP API (passenger_stop_view AC-01).

    Built without reading the configuration (default settings, no validation), opening the
    database or touching the network: the routes are registered but never resolved."""
    return create_app(Settings.model_construct(), schema_only=True).openapi()
