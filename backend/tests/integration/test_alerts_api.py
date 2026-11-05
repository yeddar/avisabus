"""`POST /api/v1/alerts` and `GET /api/v1/alerts/mine` over `gtfs_mini` and the replayed
`stop_508_peak` session (alert_create T-05).

The `FakeClock` is set inside the session. The buses are never written by hand: each test asks
`GET /arrivals` first, with the same clock, and requests one of the buses it shows.
"""

import asyncio
import contextlib
import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text
from structlog.testing import capture_logs

from avisabus.adapters.inbound.http.app import openapi_document
from avisabus.domain.models.events import Event
from avisabus.domain.ports.events import Subscription, device_channel
from tests.support.alerts_app import (
    DEVICE,
    OTHER_DEVICE,
    PROBLEM_BASE,
    GateSource,
    alerts_client,
    body_for,
    headers,
)
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import NIGHT, STOP_508_PEAK
from tests.support.stops import API, import_feed, new_engine, replay, stops_settings, token

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
LATE = datetime(2026, 11, 2, 22, 0, tzinfo=UTC)  # 23:00 in Madrid, no recording of 508 at night
ALERTS = f"{API}/alerts"
MINE = f"{API}/alerts/mine"
PROBLEM_JSON = "application/problem+json"
ALERT_FIELDS = {
    "alert_id",
    "stop_id",
    "stop_name",
    "line",
    "direction_id",
    "destination",
    "trip_id",
    "service_date",
    "needs",
    "status",
    "created_at",
    "expires_at",
}


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """`gtfs_mini` imported once; each test copies the database file (alerts are per test)."""
    path = tmp_path_factory.mktemp("alerts") / "avisabus.sqlite"
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


def _peak_clock(offset_s: float = 0) -> FakeClock:
    return FakeClock(PEAK_START + timedelta(seconds=offset_s))


async def _arrivals(client: httpx.AsyncClient, stop_id: str = "508") -> list[dict[str, Any]]:
    response = await client.get(f"{API}/stops/{stop_id}/arrivals", params={"t": token(stop_id)})
    assert response.status_code == 200
    arrivals: list[dict[str, Any]] = response.json()["arrivals"]
    return arrivals


async def _requestable(
    client: httpx.AsyncClient, stop_id: str = "508", line: str | None = None
) -> dict[str, Any]:
    return next(
        a
        for a in await _arrivals(client, stop_id)
        if a["can_alert"] and (line is None or a["line"] == line)
    )


async def _post(
    client: httpx.AsyncClient, body: dict[str, Any], device: str = DEVICE
) -> httpx.Response:
    return await client.post(ALERTS, json=body, headers=headers(device))


def _z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _files_containing(folder: Path, pattern: str, value: str) -> list[Path]:
    return [path for path in folder.glob(pattern) if value.encode() in path.read_bytes()]


async def _queued_event(subscription: Subscription) -> Event | None:
    """The event already queued in the subscription, if any, without letting time pass: the
    publisher is synchronous, so an event of a request is queued when its response arrives."""
    task = asyncio.ensure_future(subscription.next_event())
    await asyncio.sleep(0)  # one turn of the loop, no real wait
    if task.done():
        return task.result()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return None


# --- Create (AC-02) ---


@pytest.mark.spec("alert_create.AC-02")
@pytest.mark.spec("alert_create.AC-14")
async def test_creates_the_alert_for_a_bus_shown_by_the_arrivals(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        arrival = await _requestable(client, line="93")
        body = body_for(arrival, "508", token("508"), needs=["VISUAL", "RAMP"])
        response = await _post(client, body)
    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    alert = response.json()
    assert set(alert) == ALERT_FIELDS
    assert uuid.UUID(alert["alert_id"]).version == 4
    assert alert == {
        "alert_id": alert["alert_id"],
        "stop_id": "508",
        "stop_name": "Parc de l'Oest - Enguera",
        "line": "93",
        "direction_id": 0,
        "destination": arrival["destination"],
        "trip_id": arrival["vehicle"]["trip_id"],
        "service_date": arrival["vehicle"]["service_date"],
        "needs": ["RAMP", "VISUAL"],
        "status": "PENDING_DRIVER",
        "created_at": _z(clock.now()),
        "expires_at": _z(clock.now() + timedelta(minutes=30)),
    }


@pytest.mark.spec("alert_create.AC-02")
async def test_alert_ids_are_random(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        arrival = await _requestable(client, line="93")
        first = await _post(client, body_for(arrival, "508", token("508")))
        second = await _post(client, body_for(arrival, "508", token("508")), OTHER_DEVICE)
    assert (first.status_code, second.status_code) == (201, 201)
    assert first.json()["alert_id"] != second.json()["alert_id"]


@pytest.mark.spec("alert_create.AC-02")
async def test_a_scheduled_bus_can_be_requested_when_the_sae_fails(engine: Engine) -> None:
    clock = FakeClock(LATE)
    source, _ = replay(NIGHT, clock)
    async with alerts_client(engine, clock, source) as (client, _):
        response = await client.get(f"{API}/stops/508/arrivals", params={"t": token("508")})
        assert response.json()["source"] == "SCHEDULED"
        arrival = await _requestable(client)
        created = await _post(client, body_for(arrival, "508", token("508")))
    assert created.status_code == 201
    assert created.json()["trip_id"] == arrival["vehicle"]["trip_id"]


# --- The bus must be requestable (AC-03) ---


@pytest.mark.spec("alert_create.AC-03")
async def test_validation_reuses_the_cached_arrivals(engine: Engine) -> None:
    clock = _peak_clock()
    source, counting = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        arrival = await _requestable(client, line="93")
        assert counting.calls == 1
        created = await _post(client, body_for(arrival, "508", token("508")))
        bad = body_for(arrival, "508", token("508"), line="70", trip_id="nope")
        rejected = await _post(client, bad)
    assert (created.status_code, rejected.status_code) == (201, 422)
    assert counting.calls == 1  # no extra request to the SAE


@pytest.mark.spec("alert_create.AC-03")
async def test_unknown_bus_is_not_requestable(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        arrival = await _requestable(client, line="93")
        responses = [
            await _post(client, body_for(arrival, "508", token("508"), **changes))
            for changes in (
                {"trip_id": "93_does_not_exist"},
                {"service_date": "2026-11-03"},
                {"direction_id": 1},
                {"line": "70"},
            )
        ]
        mine = await client.get(MINE, headers=headers())
    for response in responses:
        assert response.status_code == 422
        assert response.headers["content-type"] == PROBLEM_JSON
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json() == {
            "type": PROBLEM_BASE + "bus-not-requestable",
            "title": "Unprocessable Entity",
            "status": 422,
        }
    assert mine.json() == {"alerts": []}


@pytest.mark.spec("alert_create.AC-03")
async def test_a_bus_that_already_passed_is_not_requestable(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        first = (await _arrivals(client))[0]
        clock.advance(timedelta(minutes=25))  # the session goes on; that bus has gone by
        later = await _arrivals(client)
        assert first["vehicle"]["trip_id"] not in [a["vehicle"]["trip_id"] for a in later]
        response = await _post(client, body_for(first, "508", token("508")))
    assert response.status_code == 422
    assert response.json()["type"] == PROBLEM_BASE + "bus-not-requestable"


@pytest.mark.spec("alert_create.AC-03")
async def test_a_bus_more_than_30_min_ahead_is_not_requestable(engine: Engine) -> None:
    # Timetable at 23:00 in Madrid: the 70 at 23:33:38 has its trip but is too far ahead.
    clock = FakeClock(LATE)
    source, _ = replay(NIGHT, clock)
    async with alerts_client(engine, clock, source) as (client, _):
        far = next(
            a
            for a in await _arrivals(client)
            if a["line"] == "70" and a["vehicle"] is not None and not a["can_alert"]
        )
        assert datetime.fromisoformat(far["arrival_at"]) - clock.now() > timedelta(minutes=30)
        response = await _post(client, body_for(far, "508", token("508")))
        mine = await client.get(MINE, headers=headers())
    assert response.status_code == 422
    assert response.json()["type"] == PROBLEM_BASE + "bus-not-requestable"
    assert mine.json() == {"alerts": []}


# --- Stop and device (AC-04, AC-05) ---


@pytest.mark.spec("alert_create.AC-04")
async def test_invalid_token_or_unknown_stop_is_the_stop_404(engine: Engine) -> None:
    clock = _peak_clock()
    source, counting = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        stop_404 = await client.get(f"{API}/stops/508", params={"t": "A" * 22})
        bodies = [
            {"stop_id": "508", "token": "A" * 22},
            {"stop_id": "508", "token": ""},
            {"stop_id": "508", "token": token("2070")},
            {"stop_id": "999999", "token": token("999999")},
        ]
        base = {"line": "93", "direction_id": 0, "trip_id": "t", "service_date": "2026-11-02"}
        responses = [await _post(client, {**base, **body, "needs": []}) for body in bodies]
    assert stop_404.status_code == 404
    for response in responses:
        assert response.status_code == 404
        assert response.headers["content-type"] == PROBLEM_JSON
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json() == stop_404.json()
    assert counting.calls == 0


@pytest.mark.spec("alert_create.AC-05")
@pytest.mark.spec("alert_create.AC-14")
@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "not-a-uuid",
        "3F2B8C1E-9A4D-4E6F-8B2A-1C3D5E7F9A0B",  # not canonical
        "3f2b8c1e-9a4d-1e6f-8b2a-1c3d5e7f9a0b",  # version 1
    ],
)
async def test_missing_or_invalid_device_id_is_a_400(engine: Engine, header: str | None) -> None:
    clock = _peak_clock()
    source, counting = replay(STOP_508_PEAK, clock, start=PEAK_START)
    sent = {} if header is None else {"X-Device-Id": header}
    body = {
        "stop_id": "508",
        "token": token("508"),
        "line": "93",
        "direction_id": 0,
        "trip_id": "t",
        "service_date": "2026-11-02",
        "needs": [],
    }
    async with alerts_client(engine, clock, source) as (client, _):
        responses = [
            await client.post(ALERTS, json=body, headers=sent),
            await client.get(MINE, headers=sent),
        ]
    for response in responses:
        assert response.status_code == 400
        assert response.headers["content-type"] == PROBLEM_JSON
        assert response.headers["Cache-Control"] == "no-store"
        assert response.json() == {
            "type": PROBLEM_BASE + "invalid-device-id",
            "title": "Bad Request",
            "status": 400,
        }
    assert counting.calls == 0


# --- Needs (AC-06) ---


@pytest.mark.spec("alert_create.AC-06")
@pytest.mark.spec("alert_create.AC-14")
@pytest.mark.parametrize(
    "needs",
    [
        ["RAMP", "RAMP"],
        ["SEAT", "VISUAL", "SEAT"],
        ["WHEELCHAIR"],
        ["ramp"],
        "RAMP",
        None,
        [1],
    ],
)
async def test_invalid_or_repeated_needs_are_a_422(engine: Engine, needs: Any) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        arrival = await _requestable(client, line="93")
        response = await _post(client, body_for(arrival, "508", token("508"), needs=needs))
        mine = await client.get(MINE, headers=headers())
    assert response.status_code == 422
    assert response.headers["Cache-Control"] == "no-store"
    assert mine.json() == {"alerts": []}


@pytest.mark.spec("alert_create.AC-06")
@pytest.mark.parametrize(
    ("needs", "canonical"),
    [
        ([], []),
        (["VISUAL"], ["VISUAL"]),
        (["SEAT", "EXTRA_TIME"], ["EXTRA_TIME", "SEAT"]),
        (["VISUAL", "SEAT", "EXTRA_TIME", "RAMP"], ["RAMP", "EXTRA_TIME", "SEAT", "VISUAL"]),
    ],
)
async def test_needs_are_answered_in_canonical_order(
    engine: Engine, needs: list[str], canonical: list[str]
) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        arrival = await _requestable(client, line="93")
        response = await _post(client, body_for(arrival, "508", token("508"), needs=needs))
        mine = await client.get(MINE, headers=headers())
    assert response.status_code == 201
    assert response.json()["needs"] == canonical
    assert mine.json()["alerts"][0]["needs"] == canonical


async def test_other_body_errors_are_a_422(engine: Engine) -> None:
    clock = _peak_clock()
    source, counting = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        arrival = await _requestable(client, line="93")
        good = body_for(arrival, "508", token("508"))
        responses = [
            await _post(client, {k: v for k, v in good.items() if k != "trip_id"}),
            await _post(client, {**good, "service_date": "yesterday"}),
            await _post(client, {**good, "direction_id": "zero"}),
            await client.post(ALERTS, content=b"{", headers=headers()),
        ]
    assert [r.status_code for r in responses] == [422, 422, 422, 422]
    assert counting.calls == 1


# --- One alert per device, stop and line (AC-07) ---


@pytest.mark.spec("alert_create.AC-07")
async def test_second_request_at_the_same_stop_and_line_returns_the_first(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, built):
        the_93 = [a for a in await _arrivals(client) if a["line"] == "93" and a["can_alert"]]
        assert len(the_93) >= 2
        first = await _post(client, body_for(the_93[0], "508", token("508"), needs=["RAMP"]))
        subscription = built.realtime.publisher.subscribe(device_channel(built.device_hash()))
        clock.advance(timedelta(seconds=10))
        # Another bus of the same line, other needs: still the first alert, untouched.
        again = await _post(client, body_for(the_93[1], "508", token("508"), needs=["SEAT"]))
        mine = await client.get(MINE, headers=headers())
        assert await _queued_event(subscription) is None  # no events for a 200
        subscription.close()
    assert (first.status_code, again.status_code) == (201, 200)
    assert again.headers["Cache-Control"] == "no-store"
    assert again.json() == first.json()
    assert mine.json() == {"alerts": [first.json()]}


@pytest.mark.spec("alert_create.AC-07")
async def test_two_simultaneous_requests_leave_a_single_alert(engine: Engine) -> None:
    clock = _peak_clock()
    cached, counting = replay(STOP_508_PEAK, clock, start=PEAK_START)
    gate = GateSource(cached, parties=2)
    async with alerts_client(engine, clock, gate) as (client, _):
        gate.open.set()  # let the GET through
        arrival = await _requestable(client, line="93")
        gate.open.clear()
        gate.waiting = 0
        body = body_for(arrival, "508", token("508"))
        responses = await asyncio.gather(_post(client, body), _post(client, body))
        mine = await client.get(MINE, headers=headers())
    assert gate.waiting == 2  # both requests got past the duplicate check
    assert sorted(r.status_code for r in responses) == [200, 201]
    assert responses[0].json() == responses[1].json()
    assert mine.json() == {"alerts": [responses[0].json()]}
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM alert")).scalar_one() == 1
    assert counting.calls == 1


# --- Rate limiting (AC-08) ---


@pytest.mark.spec("alert_create.AC-08")
@pytest.mark.spec("alert_create.AC-14")
async def test_device_limit_answers_429_with_retry_after(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    settings = stops_settings(alert_rate_device=2, alert_rate_window_min=10)
    async with alerts_client(engine, clock, source, settings) as (client, _):
        arrival = await _requestable(client, line="93")
        bad = body_for(arrival, "508", token("508"), trip_id="nope")
        statuses = []
        for _ in range(2):
            statuses.append((await _post(client, bad)).status_code)
            clock.advance(timedelta(minutes=1))
        arrival = await _requestable(client, line="93")  # a bus still shown 2 min later
        limited = await _post(client, body_for(arrival, "508", token("508")))
        other_device = await _post(client, body_for(arrival, "508", token("508")), OTHER_DEVICE)
    assert statuses == [422, 422]  # rejected requests count too
    assert limited.status_code == 429
    assert limited.headers["content-type"] == PROBLEM_JSON
    assert limited.headers["Cache-Control"] == "no-store"
    # Attempts at 0, 1 and 2 min: room again once those at 0 and 1 min left (at 11 min).
    assert limited.headers["Retry-After"] == str(9 * 60)
    assert limited.json() == {
        "type": PROBLEM_BASE + "rate-limited",
        "title": "Too Many Requests",
        "status": 429,
    }
    assert other_device.status_code == 201


@pytest.mark.spec("alert_create.AC-08")
async def test_ip_limit_counts_every_device(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    settings = stops_settings(alert_rate_ip=3)
    devices = [str(uuid.UUID(int=n, version=4)) for n in range(4)]
    async with alerts_client(engine, clock, source, settings, client_ip="198.51.100.7") as (
        client,
        _,
    ):
        arrival = await _requestable(client, line="93")
        body = body_for(arrival, "508", token("508"))
        statuses = [(await _post(client, body, device)).status_code for device in devices]
    assert statuses == [201, 201, 201, 429]


@pytest.mark.spec("alert_create.AC-08")
async def test_duplicates_do_not_count_and_the_window_slides(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    settings = stops_settings(alert_rate_device=2, alert_rate_window_min=1)
    async with alerts_client(engine, clock, source, settings) as (client, _):
        arrival = await _requestable(client, line="93")
        body = body_for(arrival, "508", token("508"))
        statuses = [(await _post(client, body)).status_code for _ in range(6)]
        bad = body_for(arrival, "508", token("508"), line="70", trip_id="nope")
        statuses.append((await _post(client, bad)).status_code)
        statuses.append((await _post(client, bad)).status_code)
        clock.advance(timedelta(minutes=1))
        statuses.append((await _post(client, bad)).status_code)
    assert statuses == [201, 200, 200, 200, 200, 200, 422, 429, 422]


@pytest.mark.spec("alert_create.AC-08")
@pytest.mark.spec("alert_create.AC-13")
async def test_limits_and_their_keys_are_never_logged(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    settings = stops_settings(alert_rate_device=1)
    with capture_logs() as logs:
        async with alerts_client(engine, clock, source, settings, client_ip="203.0.113.9") as (
            client,
            built,
        ):
            arrival = await _requestable(client, line="93")
            body = body_for(arrival, "508", token("508"), needs=["RAMP", "VISUAL"])
            created = await _post(client, body)
            limited = await _post(client, body_for(arrival, "508", token("508"), line="70"))
            device_hash = built.device_hash()
    assert (created.status_code, limited.status_code) == (201, 429)
    rejected = [log for log in logs if log["event"] == "alert.rejected"]
    assert [(log["reason"], log["stop_id"]) for log in rejected] == [("rate_limited", "508")]
    logged = json.dumps(logs, default=str)
    for secret in (DEVICE, device_hash, "203.0.113.9", "RAMP", "VISUAL", "device:", "ip:"):
        assert secret not in logged


# --- Confirmation (AC-09) ---


@pytest.mark.spec("alert_create.AC-09")
async def test_the_device_channel_gets_alert_registered_at_once(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, built):
        arrival = await _requestable(client, line="93")
        subscription = built.realtime.publisher.subscribe(device_channel(built.device_hash()))
        other = built.realtime.publisher.subscribe(device_channel(built.device_hash(OTHER_DEVICE)))
        response = await _post(client, body_for(arrival, "508", token("508")))
        # Already published when the 201 arrives: well within the 5 s of RNF-02.
        event = await _queued_event(subscription)
        assert await _queued_event(other) is None
        subscription.close()
        other.close()
    assert response.status_code == 201
    assert event is not None
    assert event.message() == {"type": "alert.registered", "alert": response.json()}


# --- My alerts (AC-10) ---


@pytest.mark.spec("alert_create.AC-10")
@pytest.mark.spec("alert_create.AC-14")
async def test_my_alerts_in_every_stop_by_creation(engine: Engine) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, _):
        empty = await client.get(MINE, headers=headers())
        at_2070 = await _requestable(client, "2070", line="98")
        first = await _post(client, body_for(at_2070, "2070", token("2070"), needs=["SEAT"]))
        clock.advance(timedelta(seconds=30))
        at_508 = await _requestable(client, "508", line="93")
        second = await _post(client, body_for(at_508, "508", token("508")))
        clock.advance(timedelta(seconds=30))
        at_508_70 = await _requestable(client, "508", line="70")
        third = await _post(client, body_for(at_508_70, "508", token("508")))
        theirs = await _post(client, body_for(at_508, "508", token("508")), OTHER_DEVICE)
        mine = await client.get(MINE, headers=headers())
        other = await client.get(MINE, headers=headers(OTHER_DEVICE))
    assert empty.status_code == 200
    assert empty.headers["Cache-Control"] == "no-store"
    assert empty.json() == {"alerts": []}
    assert [r.status_code for r in (first, second, third, theirs)] == [201, 201, 201, 201]
    assert mine.status_code == 200
    assert mine.headers["Cache-Control"] == "no-store"
    assert mine.json() == {"alerts": [first.json(), second.json(), third.json()]}
    assert other.json() == {"alerts": [theirs.json()]}


# --- Storage (AC-12) ---


@pytest.mark.spec("alert_create.AC-12")
async def test_alerts_survive_a_restart_and_only_the_hash_is_stored(
    engine: Engine, tmp_path: Path
) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    async with alerts_client(engine, clock, source) as (client, built):
        arrival = await _requestable(client, line="93")
        body = body_for(arrival, "508", token("508"), needs=["EXTRA_TIME", "VISUAL"])
        created = await _post(client, body)
        device_hash = built.device_hash()
    engine.dispose()

    # A new application over the same database file ("restart").
    restarted = new_engine(tmp_path / "avisabus.sqlite")
    try:
        source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
        async with alerts_client(restarted, clock, source) as (client, _):
            mine = await client.get(MINE, headers=headers())
            again = await _post(client, body)
        with restarted.connect() as conn:
            rows = conn.execute(text("SELECT device_hash, needs FROM alert")).fetchall()
            names = [r[0] for r in conn.execute(text("SELECT name FROM sqlite_master"))]
    finally:
        restarted.dispose()
    assert mine.json() == {"alerts": [created.json()]}
    assert again.status_code == 200
    assert [tuple(row) for row in rows] == [(device_hash, "EXTRA_TIME,VISUAL")]
    assert device_hash != DEVICE
    # The identifier in clear is nowhere in the database files.
    assert not _files_containing(tmp_path, "avisabus.sqlite*", DEVICE)
    assert not [name for name in names if "need" in name or "device" in name]


# --- Logs (AC-13) ---


@pytest.mark.spec("alert_create.AC-13")
async def test_created_and_rejected_alerts_are_logged_without_personal_data(
    engine: Engine,
) -> None:
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    with capture_logs() as logs:
        async with alerts_client(engine, clock, source, client_ip="192.0.2.44") as (
            client,
            built,
        ):
            arrival = await _requestable(client, line="93")
            body = body_for(arrival, "508", token("508"), needs=["RAMP", "SEAT"])
            created = await _post(client, body)
            await _post(client, body)  # duplicate
            await _post(client, body_for(arrival, "508", token("508"), line="70", trip_id="x"))
            device_hash = built.device_hash()
    alert = created.json()
    assert [
        {k: v for k, v in log.items() if k != "log_level"}
        for log in logs
        if log["event"] == "alert.created"
    ] == [
        {
            "event": "alert.created",
            "alert_id": alert["alert_id"],
            "stop_id": "508",
            "line": "93",
            "direction_id": 0,
            "status": "PENDING_DRIVER",
        }
    ]
    rejected = [log for log in logs if log["event"] == "alert.rejected"]
    assert [(log["reason"], log["stop_id"]) for log in rejected] == [("bus_not_requestable", "508")]
    logged = json.dumps(logs, default=str)
    for secret in (DEVICE, device_hash, "192.0.2.44", "RAMP", "SEAT", "needs"):
        assert secret not in logged


# --- Errors and contract (AC-14) ---


async def test_without_feed_the_alerts_answer_503(tmp_path: Path) -> None:
    empty = new_engine(tmp_path / "empty.sqlite")
    clock = _peak_clock()
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    body = {
        "stop_id": "508",
        "token": token("508"),
        "line": "93",
        "direction_id": 0,
        "trip_id": "t",
        "service_date": "2026-11-02",
        "needs": [],
    }
    try:
        async with alerts_client(empty, clock, source) as (client, _):
            response = await _post(client, body)
    finally:
        empty.dispose()
    assert response.status_code == 503
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["type"] == PROBLEM_BASE + "network-unavailable"


@pytest.mark.spec("alert_create.AC-14")
def test_openapi_describes_the_alert_endpoints_with_examples() -> None:
    document = openapi_document()
    post = document["paths"]["/api/v1/alerts"]["post"]
    mine = document["paths"]["/api/v1/alerts/mine"]["get"]
    assert {"201", "200", "400", "404", "422", "429", "503"} <= set(post["responses"])
    assert {"200", "400"} <= set(mine["responses"])
    assert "Retry-After" in post["responses"]["429"]["headers"]
    for status in ("400", "404", "422", "429", "503"):
        assert post["responses"][status]["content"]["application/problem+json"]["example"]
    validation = post["responses"]["422"]["content"]["application/json"]["schema"]["$ref"]
    assert validation.removeprefix("#/components/schemas/") in document["components"]["schemas"]
    assert {p["name"] for p in post["parameters"]} == {"x-device-id"}
    schemas = document["components"]["schemas"]
    request = schemas["CreateAlertRequest"]
    assert set(request["required"]) == {
        "stop_id",
        "token",
        "line",
        "direction_id",
        "trip_id",
        "service_date",
        "needs",
    }
    assert request["examples"]
    alert = schemas["AlertSchema"]
    assert set(alert["properties"]) == ALERT_FIELDS
    assert set(alert["required"]) == ALERT_FIELDS
    assert alert["examples"]
    assert schemas["Need"]["enum"] == ["RAMP", "EXTRA_TIME", "SEAT", "VISUAL"]
    assert set(schemas["AlertStatus"]["enum"]) == {"PENDING_DRIVER", "DELIVERED"}
    assert schemas["MyAlertsResponse"]["examples"]
