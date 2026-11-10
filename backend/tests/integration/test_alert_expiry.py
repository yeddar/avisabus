"""Alert expiry over `gtfs_mini`, the replayed `stop_508_peak` session behind the production SAE
cache, SQLite and `/ws/passenger` (alert_expiry T-03, T-04).

The alerts are created with `POST /alerts` for buses shown by `GET /arrivals`; the expiry cycles
are run by calling `tick()` with a `FakeClock` (no time passes for real). Instants of the session
(exploration E-01, `progress/explore_passage_samples/timeline_20s.txt`): the 93 `…_122` is at
6 min at 0 s, at 0 min from 720 s to 760 s and gone at 780 s (passage); the 98 `…_059` at 2070 is
last seen at 320 s at 4 min and is gone from 340 s on.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text
from starlette.testclient import TestClient
from structlog.testing import capture_logs

from avisabus.adapters.outbound.persistence.sqlite_alerts import SqliteAlertRepository
from avisabus.adapters.outbound.sae.cache import CachedArrivalsSource
from avisabus.adapters.outbound.sae.replay import SaeReplayArrivalsSource
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalsSnapshot
from avisabus.domain.ports.events import Subscription, device_channel
from tests.integration.test_main_composition import _run_main
from tests.support.alerts_app import AlertsApp, body_for, build_alerts_app, headers
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import STOP_508_PEAK
from tests.support.stops import API, import_feed, new_engine, token
from tests.support.ws import receive_json_soon

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
ALERTS = f"{API}/alerts"
WS = "/ws/passenger"
WINDOW = timedelta(minutes=2)
DEVICES = [f"00000000-0000-4000-8000-00000000000{n}" for n in range(1, 4)]


def at(seconds: float) -> datetime:
    return PEAK_START + timedelta(seconds=seconds)


class SaeProbe:
    """The replayed SAE, recording each request that reaches it (behind the cache) and failing
    on demand like an unavailable SAE."""

    def __init__(self, clock: FakeClock) -> None:
        self.inner = SaeReplayArrivalsSource(STOP_508_PEAK, clock, PEAK_START)
        self.requests: list[str] = []
        self.failing = False

    async def get_arrivals(self, stop_id: str) -> ArrivalsSnapshot:
        self.requests.append(stop_id)
        if self.failing:
            raise ArrivalsUnavailableError(stop_id, "timeout")
        return await self.inner.get_arrivals(stop_id)


def build(engine: Engine, clock: FakeClock) -> tuple[AlertsApp, SaeProbe]:
    """Composition of `avisabus.main`, with the production cache settings (TTL 20 s)."""
    probe = SaeProbe(clock)
    cache = CachedArrivalsSource(
        inner=probe,
        clock=clock,
        ttl=timedelta(seconds=20),
        error_ttl=timedelta(seconds=5),
        max_concurrency=4,
    )
    return build_alerts_app(engine, clock, cache), probe


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`gtfs_mini` imported once; each test copies the database file (alerts are per test)."""
    path = tmp_path_factory.mktemp("alert_expiry") / "avisabus.sqlite"
    engine = new_engine(path)
    import_feed(engine, GTFS_MINI)
    engine.dispose()
    return path


@pytest.fixture
def db_path(mini_feed: Path, tmp_path: Path) -> Path:
    path = tmp_path / "avisabus.sqlite"
    path.write_bytes(mini_feed.read_bytes())
    return path


@pytest.fixture
def engine(db_path: Path) -> Iterator[Engine]:
    engine = new_engine(db_path)
    yield engine
    engine.dispose()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(PEAK_START)


@asynccontextmanager
async def client_of(built: AlertsApp) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(
        app=built.app, raise_app_exceptions=False, client=("127.0.0.1", 50000)
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def _arrival(arrivals: dict[str, Any], line: str, trip_suffix: str | None) -> dict[str, Any]:
    return next(
        a
        for a in arrivals["arrivals"]
        if a["can_alert"]
        and a["line"] == line
        and (trip_suffix is None or a["vehicle"]["trip_id"].endswith(trip_suffix))
    )


async def _create(
    client: httpx.AsyncClient,
    stop_id: str,
    line: str,
    device: str = DEVICES[0],
    trip_suffix: str | None = None,
) -> dict[str, Any]:
    response = await client.get(f"{API}/stops/{stop_id}/arrivals", params={"t": token(stop_id)})
    arrival = _arrival(response.json(), line, trip_suffix)
    created = await client.post(
        ALERTS,
        json=body_for(arrival, stop_id, token(stop_id), needs=["RAMP", "VISUAL"]),
        headers=headers(device),
    )
    assert created.status_code == 201
    alert: dict[str, Any] = created.json()
    return alert


def _rows(engine: Engine) -> list[tuple[str, str]]:
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT alert_id, needs FROM alert ORDER BY alert_id"))
        return [(row[0], row[1]) for row in rows]


def _alert_ids(engine: Engine) -> set[str]:
    return {alert_id for alert_id, _ in _rows(engine)}


async def _queued(subscriptions: list[Subscription]) -> list[dict[str, object]]:
    """Events already queued in the subscriptions, without letting time pass: the publisher is
    synchronous, so an event is queued when the cycle that published it returns."""
    events: list[dict[str, object]] = []
    for subscription in subscriptions:
        while True:
            task = asyncio.ensure_future(subscription.next_event())
            await asyncio.sleep(0)  # one turn of the loop, no real wait
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                break
            events.append(task.result().message())
    return events


# --- One query per stop through the shared cache (AC-04) ---


@pytest.mark.spec("alert_expiry.AC-04")
async def test_each_stop_with_alerts_is_read_once_per_cycle_through_the_shared_cache(
    engine: Engine, clock: FakeClock
) -> None:
    built, sae = build(engine, clock)
    async with client_of(built) as client:
        await _create(client, "508", "93", DEVICES[0])
        await _create(client, "508", "93", DEVICES[1])
        await _create(client, "508", "70", DEVICES[0])
        on_2070 = await _create(client, "2070", "98", DEVICES[0])
        assert sorted(sae.requests) == ["2070", "508"]  # the creations shared the cache

        # Same instant: the watcher reuses the cached answers of the stops.
        sae.requests.clear()
        await built.expiry.watch_passages.tick()
        assert sae.requests == []

        # 20 s later the cache has expired: one request per stop, whatever its alerts.
        clock.advance(timedelta(seconds=20))
        await built.expiry.watch_passages.tick()
        assert sorted(sae.requests) == ["2070", "508"]
        await built.expiry.expire_due_alerts.tick()  # the ticker never asks the SAE
        assert sorted(sae.requests) == ["2070", "508"]

        # A stop without alerts is not read.
        cancel = await client.delete(f"{ALERTS}/{on_2070['alert_id']}", headers=headers(DEVICES[0]))
        assert cancel.status_code == 204
        sae.requests.clear()
        clock.advance(timedelta(seconds=20))
        await built.expiry.watch_passages.tick()
        assert sae.requests == ["508"]
    assert len(_rows(engine)) == 3


# --- An unavailable SAE (AC-03) ---


@pytest.mark.spec("alert_expiry.AC-03")
async def test_a_failing_sae_neither_tracks_nor_passes(engine: Engine, clock: FakeClock) -> None:
    built, sae = build(engine, clock)
    watcher = built.expiry.watch_passages
    repository = SqliteAlertRepository(engine)
    async with client_of(built) as client:
        alert = await _create(client, "508", "93", trip_suffix="_122")
        alert_id = alert["alert_id"]
        clock.set(at(760))  # the 93 _122 at 0 min
        await watcher.tick()
        tracked = repository.get(alert_id)
        assert tracked is not None
        assert tracked.tracking.last_seen_at == at(760)
        assert watcher.seen_in_last_observation(alert_id) is True

        # The SAE fails right when the bus passes: the timetable fallback changes nothing.
        sae.failing = True
        subscriptions = [
            built.realtime.publisher.subscribe(device_channel(built.device_hash(DEVICES[0])))
        ]
        for seconds in (780, 790):
            clock.set(at(seconds))
            await watcher.tick()
        assert repository.get(alert_id) == tracked
        assert watcher.seen_in_last_observation(alert_id) is False
        assert await _queued(subscriptions) == []
        sae_calls_while_failing = sae.requests.count("508")

        # Back in real time, the trip is gone and it was arriving: it has passed.
        sae.failing = False
        clock.set(at(800))
        await watcher.tick()
        events = await _queued(subscriptions)
    assert sae_calls_while_failing >= 3
    assert repository.get(alert_id) is None
    assert events == [{"type": "alert.expired", "alert_id": alert_id, "reason": "PASSED"}]


# --- Effects (AC-08) ---


@pytest.mark.spec("alert_expiry.AC-08")
def test_an_expired_alert_reaches_the_device_sockets_and_its_row_is_deleted(
    engine: Engine, clock: FakeClock
) -> None:
    built, _ = build(engine, clock)
    watcher = built.expiry.watch_passages
    mine, theirs = DEVICES[0], DEVICES[1]
    with capture_logs() as logs, TestClient(built.app) as client:
        arrivals = client.get(f"{API}/stops/508/arrivals", params={"t": token("508")}).json()
        body = body_for(_arrival(arrivals, "93", "_122"), "508", token("508"), needs=["RAMP"])
        alert = client.post(ALERTS, json=body, headers=headers(mine)).json()
        other = body_for(_arrival(arrivals, "70", None), "508", token("508"), needs=["SEAT"])
        kept = client.post(ALERTS, json=other, headers=headers(theirs)).json()
        with (
            client.websocket_connect(WS) as tab,
            client.websocket_connect(WS) as other_tab,
            client.websocket_connect(WS) as other_device,
        ):
            for ws, device in ((tab, mine), (other_tab, mine), (other_device, theirs)):
                ws.send_json({"type": "hello", "device_id": device})
                assert receive_json_soon(ws)["type"] == "alerts.snapshot"
            assert client.portal is not None
            for seconds in (760, 780):
                clock.set(at(seconds))
                client.portal.call(watcher.tick)
            expired = {"type": "alert.expired", "alert_id": alert["alert_id"], "reason": "PASSED"}
            assert receive_json_soon(tab) == expired
            assert receive_json_soon(other_tab) == expired
            with pytest.raises(AssertionError, match="sent nothing"):
                receive_json_soon(other_device)
            mine_now = client.get(f"{ALERTS}/mine", headers=headers(mine)).json()
        device_hash = built.device_hash(mine)
    # Deleted with its needs; the other device's alert is still there.
    assert _rows(engine) == [(kept["alert_id"], "SEAT")]
    assert mine_now == {"alerts": []}
    expired_logs = [
        {k: v for k, v in log.items() if k != "log_level"}
        for log in logs
        if log["event"] == "alert.expired"
    ]
    assert expired_logs == [
        {
            "event": "alert.expired",
            "alert_id": alert["alert_id"],
            "stop_id": "508",
            "line": "93",
            "reason": "PASSED",
        }
    ]
    logged = json.dumps([log for log in logs if log["event"] != "alert.created"], default=str)
    for secret in (mine, device_hash, "RAMP", "needs"):
        assert secret not in logged


# --- Tracking in the database (AC-09) ---


@pytest.mark.spec("alert_expiry.AC-09")
async def test_the_tracking_survives_a_restart(db_path: Path, clock: FakeClock) -> None:
    first_engine = new_engine(db_path)
    built, _ = build(first_engine, clock)
    async with client_of(built) as client:
        alert = await _create(client, "508", "93", trip_suffix="_122")
    alert_id = alert["alert_id"]
    created = SqliteAlertRepository(first_engine).get(alert_id)
    assert created is not None
    # On creation it was 6 min away: that alone would never be a passage.
    assert created.tracking.last_arrival_at - created.tracking.last_seen_at > WINDOW  # type: ignore[operator]

    clock.set(at(760))
    await built.expiry.watch_passages.tick()
    first_engine.dispose()  # the application stops

    second_engine = new_engine(db_path)  # and starts again: nothing in memory
    restarted, _ = build(second_engine, clock)
    stored = SqliteAlertRepository(second_engine).get(alert_id)
    assert stored is not None
    assert stored.tracking.last_seen_at == at(760)
    assert stored.tracking.last_arrival_at - at(760) <= WINDOW
    assert restarted.expiry.watch_passages.seen_in_last_observation(alert_id) is False

    clock.set(at(780))
    await restarted.expiry.watch_passages.tick()
    assert SqliteAlertRepository(second_engine).get(alert_id) is None
    second_engine.dispose()


# --- Next stop with the real network (AC-05) ---


@pytest.mark.spec("alert_expiry.AC-05")
async def test_a_bus_lost_far_away_expires_by_next_stop(engine: Engine, clock: FakeClock) -> None:
    """The 98 `…_059` leaves the SAE list at 4 min (E-01: not a detectable passage); it expires
    once it should be at the next stop of its trip (E-01: from 803 s)."""
    built, _ = build(engine, clock)
    watcher, ticker = built.expiry.watch_passages, built.expiry.expire_due_alerts
    subscriptions = [
        built.realtime.publisher.subscribe(device_channel(built.device_hash(DEVICES[0])))
    ]
    async with client_of(built) as client:
        alert = await _create(client, "2070", "98", trip_suffix="_059")
    assert [event["type"] for event in await _queued(subscriptions)] == ["alert.registered"]
    expired_at = None
    for seconds in range(20, 1000, 20):
        clock.set(at(seconds))
        await watcher.tick()
        await ticker.tick()
        if alert["alert_id"] not in _alert_ids(engine):
            expired_at = seconds
            break
    assert expired_at == 820
    assert await _queued(subscriptions) == [
        {"type": "alert.expired", "alert_id": alert["alert_id"], "reason": "NEXT_STOP"}
    ]


# --- Start and stop with the application (AC-10) ---

LIFESPAN_PROBE = """
import asyncio
import avisabus.main as main

expiry = main.alert_expiry
watch, ticker = expiry.watch_passages, expiry.expire_due_alerts
print("intervals:", expiry.watch_interval.total_seconds(), expiry.expiry_interval.total_seconds())
print("window:", watch._window.total_seconds(), "margin:", ticker._margin.total_seconds())
print("same arrivals:", watch._stop_arrivals is main.stop_use_cases.get_stop_arrivals)
print("same publisher:", watch._expire._events is main.realtime.publisher)
print("shared expiry:", watch._expire is ticker._expire)
print("seen from the watcher:", ticker._seen == watch.seen_in_last_observation)
print("notifier:", type(watch._expire._drivers).__name__)

def running():
    return sorted(t.get_name() for t in asyncio.all_tasks() if t.get_name().startswith("alerts."))

async def probe():
    async with main.app.router.lifespan_context(main.app):
        await asyncio.sleep(0)
        print("running:", running())
    print("running:", running())

asyncio.run(probe())
"""


@pytest.mark.spec("alert_expiry.AC-10")
def test_the_application_starts_and_stops_both_tasks(tmp_path: Path) -> None:
    result = _run_main(
        tmp_path,
        probe=LIFESPAN_PROBE,
        AVISABUS_PASSAGE_WATCH_INTERVAL_S="20",
        AVISABUS_PASSAGE_WINDOW_MIN="3",
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "intervals: 20.0 10.0",
        "window: 180.0 margin: 120.0",
        "same arrivals: True",
        "same publisher: True",
        "shared expiry: True",
        "seen from the watcher: True",
        "notifier: DemandViewNotifier",
        "running: ['alerts.expiry_ticker', 'alerts.passage_watcher']",
        "running: []",
    ]
