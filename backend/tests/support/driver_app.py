"""App with the driver endpoints over `gtfs_mini` and a FakeClock (driver_session T-05, T-06)."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

import httpx
import structlog
from sqlalchemy import Engine

from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import DriverUseCases, build_driver_use_cases
from avisabus.adapters.outbound.persistence.sqlite_driver_codes import SqliteDriverCodeRepository
from avisabus.adapters.outbound.security.hmac_driver_code_hasher import HmacDriverCodeHasher
from avisabus.adapters.outbound.security.secrets_code_generator import SecretsCodeGenerator
from avisabus.application.driver_codes import CreateDriverCode, RevokeDriverCode
from avisabus.domain.ports.clock import Clock
from avisabus.domain.ports.driver import DriverSessionListener
from tests.support.stops import SECRET, stops_settings

DRIVER_API = "/api/v1/driver"
PROBLEM_BASE = "https://avisabus/problems"
PROBLEM_JSON = "application/problem+json"


@dataclass
class IssuedCode:
    code_id: str
    plain: str


def issue_code(engine: Engine, clock: Clock, label: str = "Tablet") -> IssuedCode:
    """A code stored with the real use case, as `driver-codes create` does."""
    created = CreateDriverCode(
        repository=SqliteDriverCodeRepository(engine),
        generator=SecretsCodeGenerator(),
        hasher=HmacDriverCodeHasher(SECRET.encode()),
        clock=clock,
        logger=structlog.get_logger("tests"),
    ).execute(label)
    return IssuedCode(created.code.code_id, created.plain_code)


def revoke_code(engine: Engine, clock: Clock, code_id: str) -> None:
    RevokeDriverCode(
        repository=SqliteDriverCodeRepository(engine),
        clock=clock,
        has_open_session=lambda _code_id: False,
        logger=structlog.get_logger("tests"),
    ).execute(code_id)


def driver_use_cases(
    engine: Engine,
    clock: Clock,
    listener: DriverSessionListener | None = None,
    **settings: Any,
) -> DriverUseCases:
    return build_driver_use_cases(stops_settings(**settings), engine, clock, listener=listener)


@asynccontextmanager
async def driver_client(use_cases: DriverUseCases) -> AsyncIterator[httpx.AsyncClient]:
    """In-process HTTP client (ASGI transport, no sockets)."""
    app = create_app(stops_settings(), drivers=use_cases)
    transport = httpx.ASGITransport(
        app=app, raise_app_exceptions=False, client=("203.0.113.7", 50000)
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def login(client: httpx.AsyncClient, code: IssuedCode) -> dict[str, Any]:
    response = await client.post(f"{DRIVER_API}/sessions", json={"code": code.plain})
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body
