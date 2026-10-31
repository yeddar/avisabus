"""FastAPI application factory."""

from fastapi import FastAPI

import avisabus
from avisabus.adapters.inbound.http.errors import register_error_handlers
from avisabus.adapters.inbound.http.routes import health
from avisabus.config import Settings

API_PREFIX = "/api/v1"


def create_app(settings: Settings) -> FastAPI:
    app = FastAPI(title="AvisaBus", version=avisabus.__version__)
    app.state.settings = settings
    register_error_handlers(app)
    app.include_router(health.router, prefix=API_PREFIX)
    return app
