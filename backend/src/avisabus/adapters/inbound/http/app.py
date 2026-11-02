"""FastAPI application factory."""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI

import avisabus
from avisabus.adapters.inbound.http.errors import register_error_handlers
from avisabus.adapters.inbound.http.routes import health
from avisabus.config import Settings

API_PREFIX = "/api/v1"


Lifespan = Callable[[FastAPI], AbstractAsyncContextManager[None]]


def create_app(settings: Settings, lifespan: Lifespan | None = None) -> FastAPI:
    """`lifespan` starts and stops the background work wired in `avisabus.main`."""
    app = FastAPI(title="AvisaBus", version=avisabus.__version__, lifespan=lifespan)
    app.state.settings = settings
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    return app
