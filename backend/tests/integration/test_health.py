from collections.abc import Iterator
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import httpx
import pytest
from sqlalchemy import Engine

import avisabus
from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import build_gtfs_status
from avisabus.config import Settings
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.stops import import_feed, new_engine

PROBLEM_JSON = "application/problem+json"
HEALTH = "/api/v1/health"
# gtfs_mini: feed_version 23-10-2026, feed_end_date 2026-11-22.
FEED = {"feed_version": "23-10-2026", "feed_end_date": "2026-11-22"}


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("health") / "avisabus.sqlite"
    engine = new_engine(path)
    import_feed(engine, GTFS_MINI)
    engine.dispose()
    return path


@pytest.fixture
def feed_engine(mini_feed: Path) -> Iterator[Engine]:
    engine = new_engine(mini_feed)
    yield engine
    engine.dispose()


async def _health(settings: Settings, engine: Engine, now: datetime) -> httpx.Response:
    app = create_app(settings, gtfs=build_gtfs_status(engine, FakeClock(now)))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(HEALTH)


@pytest.mark.spec("project_scaffold.AC-10")
@pytest.mark.spec("deployment_rpi.AC-10")
async def test_health_returns_ok_package_version_and_the_active_feed(
    settings: Settings, feed_engine: Engine
) -> None:
    response = await _health(settings, feed_engine, datetime(2026, 11, 11, 9, 0, tzinfo=UTC))
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "version": avisabus.__version__,
        "gtfs": {**FEED, "days_left": 11},
    }
    assert avisabus.__version__ == version("avisabus")


@pytest.mark.spec("deployment_rpi.AC-10")
@pytest.mark.parametrize(
    ("now", "days_left"),
    [
        (datetime(2026, 11, 21, 22, 59, tzinfo=UTC), 1),  # 23:59 of the 21st in Madrid
        (datetime(2026, 11, 21, 23, 0, tzinfo=UTC), 0),  # 00:00 of the 22nd in Madrid
        (datetime(2026, 11, 22, 22, 59, tzinfo=UTC), 0),  # last valid day, still ok
    ],
)
async def test_days_left_counts_days_in_madrid_and_the_last_day_is_still_ok(
    settings: Settings, feed_engine: Engine, now: datetime, days_left: int
) -> None:
    response = await _health(settings, feed_engine, now)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["gtfs"] == {**FEED, "days_left": days_left}


@pytest.mark.spec("deployment_rpi.AC-10")
@pytest.mark.parametrize(
    ("now", "days_left"),
    [
        (datetime(2026, 11, 22, 23, 0, tzinfo=UTC), -1),  # 00:00 of the 23rd in Madrid
        (datetime(2026, 12, 1, 12, 0, tzinfo=UTC), -9),
    ],
)
async def test_an_expired_feed_is_degraded_but_still_200(
    settings: Settings, feed_engine: Engine, now: datetime, days_left: int
) -> None:
    response = await _health(settings, feed_engine, now)
    assert response.status_code == 200
    assert response.json() == {
        "status": "degraded",
        "version": avisabus.__version__,
        "gtfs": {**FEED, "days_left": days_left},
    }


@pytest.mark.spec("deployment_rpi.AC-10")
async def test_without_a_feed_gtfs_is_null_and_degraded_but_still_200(
    settings: Settings, tmp_path: Path
) -> None:
    engine = new_engine(tmp_path / "empty.sqlite")
    try:
        response = await _health(settings, engine, datetime(2026, 11, 11, 9, 0, tzinfo=UTC))
    finally:
        engine.dispose()
    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "version": avisabus.__version__, "gtfs": None}


@pytest.mark.spec("deployment_rpi.AC-10")
async def test_an_app_without_the_network_reports_no_feed(api_client: httpx.AsyncClient) -> None:
    response = await api_client.get(HEALTH)
    assert response.status_code == 200
    assert response.json() == {"status": "degraded", "version": avisabus.__version__, "gtfs": None}


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
