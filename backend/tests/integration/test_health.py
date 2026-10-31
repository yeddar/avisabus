from importlib.metadata import version

import httpx
import pytest

import avisabus
from avisabus.adapters.inbound.http.app import create_app
from avisabus.config import Settings

PROBLEM_JSON = "application/problem+json"


@pytest.mark.spec("project_scaffold.AC-10")
async def test_health_returns_ok_and_package_version(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": avisabus.__version__}
    assert avisabus.__version__ == version("avisabus")


@pytest.mark.spec("project_scaffold.AC-11")
async def test_unhandled_exception_becomes_problem_json_without_internals(
    settings: Settings,
) -> None:
    app = create_app(settings)

    async def explode() -> None:
        raise RuntimeError("secret internal detail device_id=abc123")

    app.add_api_route("/api/v1/_test/explode", explode, methods=["GET"])
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/v1/_test/explode")

    assert response.status_code == 500
    assert response.headers["content-type"].startswith(PROBLEM_JSON)
    assert response.json() == {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
    }
    assert "secret" not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text
