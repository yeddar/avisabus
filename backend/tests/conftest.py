"""Shared fixtures. Tests never touch the network or the real clock."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest

from avisabus.adapters.inbound.http.app import create_app
from avisabus.config import Settings
from tests.support.fake_clock import FakeClock

DEFAULT_NOW = datetime(2026, 10, 31, 8, 0, tzinfo=UTC)


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock(DEFAULT_NOW)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, env="test")  # type: ignore[call-arg]


@pytest.fixture
async def api_client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    """In-process HTTP client (ASGI transport, no sockets)."""
    transport = httpx.ASGITransport(app=create_app(settings), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
