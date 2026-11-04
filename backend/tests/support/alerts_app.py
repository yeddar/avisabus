"""App with the stop, alert and real-time endpoints over `gtfs_mini` and a replayed SAE session
(alert_create). Built like `avisabus.main`, with a `FakeClock` and a fake `sleep`."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
from fastapi import FastAPI
from sqlalchemy import Engine

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import (
    AlertUseCases,
    Realtime,
    StopUseCases,
    build_alert_snapshots,
    build_alert_use_cases,
    build_realtime,
    build_stop_use_cases,
)
from avisabus.adapters.outbound.security.hmac_device_hasher import HmacDeviceHasher
from avisabus.config import Settings
from avisabus.domain.models.arrivals import ArrivalsSnapshot
from avisabus.domain.models.device import parse_device_id
from avisabus.domain.ports.arrivals import ArrivalsSource
from avisabus.domain.ports.clock import Clock
from tests.support.stops import simulated_sensor, stops_settings
from tests.support.ws import FakeSleep

DEVICE = "3f2b8c1e-9a4d-4e6f-8b2a-1c3d5e7f9a0b"
OTHER_DEVICE = "00000000-0000-4000-8000-000000000000"
PROBLEM_BASE = "https://avisabus/problems/"


@dataclass(frozen=True, slots=True)
class AlertsApp:
    app: FastAPI
    settings: Settings
    stops: StopUseCases
    alerts: AlertUseCases
    realtime: Realtime

    def device_hash(self, device: str = DEVICE) -> str:
        hasher = HmacDeviceHasher(self.settings.stop_token_secret_bytes())
        return hasher.hash(parse_device_id(device))


def build_alerts_app(
    engine: Engine,
    clock: Clock,
    source: ArrivalsSource,
    settings: Settings | None = None,
    sleep: FakeSleep | None = None,
) -> AlertsApp:
    """Same composition as `avisabus.main`."""
    settings = settings or stops_settings()
    stops = build_stop_use_cases(
        settings, engine, clock, source, simulated_sensor(settings, engine, clock), {}
    )
    realtime = build_realtime(
        settings, clock, snapshots=build_alert_snapshots(engine), sleep=sleep or FakeSleep()
    )
    alerts = build_alert_use_cases(settings, engine, clock, stops, realtime.publisher)
    app = create_app(settings, stops=stops, realtime=realtime, alerts=alerts)
    return AlertsApp(app, settings, stops, alerts, realtime)


@asynccontextmanager
async def alerts_client(
    engine: Engine,
    clock: Clock,
    source: ArrivalsSource,
    settings: Settings | None = None,
    client_ip: str = "127.0.0.1",
) -> AsyncIterator[tuple[httpx.AsyncClient, AlertsApp]]:
    built = build_alerts_app(engine, clock, source, settings)
    transport = httpx.ASGITransport(
        app=built.app, raise_app_exceptions=False, client=(client_ip, 50000)
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client, built


class GateSource:
    """Holds every request until `parties` of them are waiting, then lets them all through:
    concurrent requests are then all past their first checks at the same time."""

    def __init__(self, inner: ArrivalsSource, parties: int) -> None:
        self.inner = inner
        self.parties = parties
        self.waiting = 0
        self.open = asyncio.Event()

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        self.waiting += 1
        if self.waiting >= self.parties:
            self.open.set()
        await self.open.wait()
        return await self.inner.get_arrivals(stop_id)


def headers(device: str = DEVICE) -> dict[str, str]:
    return {"X-Device-Id": device}


def body_for(arrival: dict[str, Any], stop_id: str, token: str, **changes: Any) -> dict[str, Any]:
    """Request body for the bus of an arrival of `GET /arrivals`."""
    body = {
        "stop_id": stop_id,
        "token": token,
        "line": arrival["line"],
        "direction_id": arrival["direction_id"],
        "trip_id": arrival["vehicle"]["trip_id"],
        "service_date": arrival["vehicle"]["service_date"],
        "needs": [],
    }
    body.update(changes)
    return body
