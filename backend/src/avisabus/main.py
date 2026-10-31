"""Composition root: builds the concrete adapters and wires them into the use cases.

Run with `uvicorn avisabus.main:app`.
"""

from avisabus.adapters.inbound.http.app import create_app
from avisabus.config import Settings
from avisabus.logging import configure_logging

settings = Settings()
configure_logging(settings.log_level)
app = create_app(settings)
