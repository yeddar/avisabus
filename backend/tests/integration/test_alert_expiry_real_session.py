"""Alert expiry over the real session `stop_508_peak` and `gtfs_mini` (alert_expiry T-05, AC-11).

The session (25 min, 2 November 2026 from 20:42 in València) is replayed behind the production
SAE cache with a `FakeClock` that advances 20 s per cycle. Each bus of the 93 at 508 gets one alert
(one device per bus) with `POST /alerts` when it first appears with `can_alert`; then, every
cycle, the passage watcher and the expiry ticker run once.

Expected result (exploration E-01, `progress/explore_passage.md`, "Lo que esperaría AC-11"):
`PASSED` = 2 (`…_122` at 780 s and `…_123` at 1040 s), `NEXT_STOP` = 0, `TIMEOUT` = 0 and 3
alerts still alive (`…_124`, `…_125`, `…_126`).

Besides (a) and (b) of AC-11, the test checks the stronger rule that E-01 proposes for (a): no
`PASSED` in a cycle in which the number of arrivals of its line and direction arriving within
(its last lead + 2 min) does not decrease, i.e. while its bus is still in the SAE list with another
trip.
"""

import asyncio
import contextlib
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine

from avisabus.adapters.outbound.persistence.sqlite_alerts import SqliteAlertRepository
from avisabus.domain.ports.events import Subscription, device_channel
from tests.support.alerts_app import AlertsApp, body_for, build_alerts_app, headers
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import STOP_508_PEAK
from tests.support.stops import API, import_feed, new_engine, replay, token

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
SESSION_S = 1480
STEP = timedelta(seconds=20)
WINDOW_S = 120
STOP = "508"
LINE = "93"


@dataclass(frozen=True, slots=True)
class Seen:
    """An arrival of the 93 in one cycle."""

    trip: tuple[str, str] | None
    direction_id: int | None
    lead_s: float


@dataclass
class Tracked:
    trip: tuple[str, str]
    alert_id: str
    created_in: int
    subscription: Subscription
    reason: str | None = None
    expired_in: int | None = None


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("alert_expiry_real") / "avisabus.sqlite"
    engine = new_engine(path)
    import_feed(engine, GTFS_MINI)
    engine.dispose()
    return path


@pytest.fixture
def engine(mini_feed: Path, tmp_path: Path) -> Iterator[Engine]:
    path = tmp_path / "avisabus.sqlite"
    path.write_bytes(mini_feed.read_bytes())
    engine = new_engine(path)
    yield engine
    engine.dispose()


def _device(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


def _observation(arrivals: dict[str, Any]) -> list[Seen]:
    generated_at = datetime.fromisoformat(arrivals["generated_at"])
    seen = []
    for arrival in arrivals["arrivals"]:
        if arrival["line"] != LINE:
            continue
        vehicle = arrival["vehicle"]
        trip = None if vehicle is None else (vehicle["trip_id"], vehicle["service_date"])
        lead = datetime.fromisoformat(arrival["arrival_at"]) - generated_at
        seen.append(Seen(trip, arrival["direction_id"], lead.total_seconds()))
    return seen


async def _expiries(subscription: Subscription) -> list[dict[str, object]]:
    """Events already queued, without letting time pass (the publisher is synchronous)."""
    events: list[dict[str, object]] = []
    while True:
        task = asyncio.ensure_future(subscription.next_event())
        await asyncio.sleep(0)
        if not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            return events
        events.append(task.result().message())


async def _run_session(
    built: AlertsApp, clock: FakeClock
) -> tuple[list[list[Seen]], list[Tracked]]:
    observations: list[list[Seen]] = []
    tracked: dict[tuple[str, str], Tracked] = {}
    transport = httpx.ASGITransport(
        app=built.app, raise_app_exceptions=False, client=("127.0.0.1", 50000)
    )
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        cycle = 0
        while (clock.now() - PEAK_START).total_seconds() <= SESSION_S:
            await built.expiry.watch_passages.tick()
            await built.expiry.expire_due_alerts.tick()
            for one in tracked.values():
                for event in await _expiries(one.subscription):
                    assert event["type"] == "alert.expired"
                    assert one.reason is None, "an alert expires once"
                    one.reason, one.expired_in = str(event["reason"]), cycle

            response = await client.get(f"{API}/stops/{STOP}/arrivals", params={"t": token(STOP)})
            arrivals = response.json()
            assert arrivals["source"] == "REALTIME"
            observations.append(_observation(arrivals))
            for arrival in arrivals["arrivals"]:
                if arrival["line"] != LINE or not arrival["can_alert"]:
                    continue
                trip = (arrival["vehicle"]["trip_id"], arrival["vehicle"]["service_date"])
                if trip in tracked:
                    continue
                device = _device(len(tracked) + 1)
                created = await client.post(
                    f"{API}/alerts",
                    json=body_for(arrival, STOP, token(STOP), needs=["RAMP"]),
                    headers=headers(device),
                )
                assert created.status_code == 201, created.text
                subscription = built.realtime.publisher.subscribe(
                    device_channel(built.device_hash(device))
                )
                tracked[trip] = Tracked(trip, created.json()["alert_id"], cycle, subscription)
            clock.advance(STEP)
            cycle += 1
    return observations, list(tracked.values())


def _lead(observation: list[Seen], trip: tuple[str, str]) -> float | None:
    return next((seen.lead_s for seen in observation if seen.trip == trip), None)


def _within(observation: list[Seen], direction: int | None, limit_s: float) -> int:
    """Arrivals of the 93 in that direction arriving within `limit_s`."""
    return sum(1 for s in observation if s.direction_id == direction and s.lead_s <= limit_s)


def _direction(observations: list[list[Seen]], trip: tuple[str, str]) -> int | None:
    return next(seen.direction_id for obs in observations for seen in obs if seen.trip == trip)


@pytest.mark.spec("alert_expiry.AC-11")
async def test_alerts_on_the_93_expire_as_its_buses_pass(
    engine: Engine,
    capsys: pytest.CaptureFixture[str],
    record_property: Any,
) -> None:
    clock = FakeClock(PEAK_START)
    source, sae = replay(STOP_508_PEAK, clock, start=PEAK_START)
    built = build_alerts_app(engine, clock, source)
    observations, alerts = await _run_session(built, clock)

    reasons = Counter(alert.reason or "ALIVE" for alert in alerts)
    report = {key: reasons.get(key, 0) for key in ("PASSED", "NEXT_STOP", "TIMEOUT", "ALIVE")}
    record_property("alert_expiry_reasons", report)
    with capsys.disabled():
        print(f"\n[alert_expiry.AC-11] 93 at 508, {len(alerts)} alerts: {report}")

    passed = [alert for alert in alerts if alert.reason == "PASSED"]
    for alert in passed:
        cycle = alert.expired_in
        assert cycle is not None and cycle > 0
        # (a) as written: the observation of that cycle does not have its trip beyond 2 min.
        lead_now = _lead(observations[cycle], alert.trip)
        assert lead_now is None or lead_now <= WINDOW_S, alert
        # (a) as E-01 proposes: its bus has left the list, it is not still there with another
        # trip (the count of 93 arrivals of its direction within its last lead + 2 min drops).
        last_lead = _lead(observations[cycle - 1], alert.trip)
        assert last_lead is not None and last_lead <= WINDOW_S, alert
        direction = _direction(observations, alert.trip)

        limit = last_lead + WINDOW_S
        before = _within(observations[cycle - 1], direction, limit)
        assert _within(observations[cycle], direction, limit) < before, alert

    # (b) at least one alert passes within the two cycles after its last observation with its
    # trip arriving within 2 min.
    def promptly(alert: Tracked) -> bool:
        assert alert.expired_in is not None
        near = [
            cycle
            for cycle in range(alert.created_in, alert.expired_in)
            if (lead := _lead(observations[cycle], alert.trip)) is not None and lead <= WINDOW_S
        ]
        return bool(near) and alert.expired_in - max(near) <= 2

    assert any(promptly(alert) for alert in passed)

    # Contrast with the exploration E-01.
    assert len(observations) == 75
    assert sae.calls == 75  # one SAE request per cycle: the watcher shares the cache
    assert report == {"PASSED": 2, "NEXT_STOP": 0, "TIMEOUT": 0, "ALIVE": 3}
    outcome = {
        alert.trip[0].rsplit("_", 1)[1]: (alert.created_in, alert.reason, alert.expired_in)
        for alert in alerts
    }
    assert outcome == {
        "122": (0, "PASSED", 39),
        "123": (0, "PASSED", 52),
        "124": (39, None, None),
        "125": (52, None, None),
        "126": (61, None, None),
    }
    alive = {alert.alert_id for alert in SqliteAlertRepository(engine).list_all()}
    assert alive == {alert.alert_id for alert in alerts if alert.reason is None}
