"""`X-Device-Id` → `device_hash` dependency and its `400` (realtime_events T-04).

The route that uses the dependency exists only in this test: the alert endpoints that will use it
come with `alert_create`.
"""

from collections.abc import AsyncIterator
from typing import Annotated

import httpx
import pytest
from fastapi import Depends, FastAPI

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import build_realtime
from avisabus.adapters.inbound.http.device import device_hash_from_header
from avisabus.adapters.outbound.security.hmac_device_hasher import HmacDeviceHasher
from avisabus.config import Settings
from avisabus.domain.models.device import parse_device_id
from tests.conftest import DEFAULT_NOW
from tests.support.fake_clock import FakeClock
from tests.support.ws import FakeSleep

DEVICE = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
INVALID_DEVICE_ID = {
    "type": "https://avisabus/problems/invalid-device-id",
    "title": "Bad Request",
    "status": 400,
}


def _app(settings: Settings) -> FastAPI:
    app = create_app(
        settings, realtime=build_realtime(settings, FakeClock(DEFAULT_NOW), sleep=FakeSleep())
    )

    @app.get("/api/v1/test-only/device")
    async def device(
        device_hash: Annotated[str, Depends(device_hash_from_header)],
    ) -> dict[str, str]:
        return {"device_hash": device_hash}

    return app


@pytest.fixture
async def client(settings: Settings) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=_app(settings), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.spec("realtime_events.AC-05")
async def test_valid_header_gives_the_keyed_hash(
    client: httpx.AsyncClient, settings: Settings
) -> None:
    response = await client.get("/api/v1/test-only/device", headers={"X-Device-Id": DEVICE})
    assert response.status_code == 200
    expected = HmacDeviceHasher(settings.stop_token_secret_bytes()).hash(parse_device_id(DEVICE))
    assert response.json() == {"device_hash": expected}


@pytest.mark.spec("realtime_events.AC-04")
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-Device-Id": ""},
        {"X-Device-Id": DEVICE.upper()},
        {"X-Device-Id": "not-a-uuid"},
        {"X-Device-Id": "3f2b8c1e-9a4d-1e6f-8b2a-1c3d5e7f9a0b"},
    ],
)
async def test_missing_or_invalid_header_is_a_400_problem(
    client: httpx.AsyncClient, headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/test-only/device", headers=headers)
    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == INVALID_DEVICE_ID
    for value in headers.values():
        if value:
            assert value not in response.text
