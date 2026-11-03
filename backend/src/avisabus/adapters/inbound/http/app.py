"""FastAPI application factory."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI

import avisabus
from avisabus.adapters.inbound.http.container import StopUseCases
from avisabus.adapters.inbound.http.errors import register_error_handlers
from avisabus.adapters.inbound.http.routes import health
from avisabus.adapters.inbound.http.routes import stops as stops_routes
from avisabus.config import Settings

API_PREFIX = "/api/v1"


Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(
    settings: Settings, lifespan: Lifespan | None = None, stops: StopUseCases | None = None
) -> FastAPI:
    """`lifespan` starts and stops the background work wired in `avisabus.main`; `stops` adds
    the stop endpoints (stop_arrivals_api), which need the network and the arrivals source."""
    app = FastAPI(title="AvisaBus", version=avisabus.__version__, lifespan=lifespan)
    app.state.settings = settings
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    if stops is not None:
        app.state.stop_use_cases = stops
        app.include_router(stops_routes.router, prefix=API_PREFIX)
    return app
