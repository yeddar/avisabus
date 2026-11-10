"""Delivery and driver view end to end (driver_demand T-04): `gtfs_mini`, a replayed SAE session,
a FakeClock and a fake `sleep`. No real time passes and the network is not used.

`TestClient` runs the application in-process. The clock moves before each action so that the limit
of one view per second never has to wait (the unit tests cover the grouping).
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import Engine
from starlette.testclient import TestClient, WebSocketTestSession
from starlette.websockets import WebSocketDisconnect
from structlog.testing import capture_logs

from avisabus.adapters.inbound.http.access_log import (
    SERVER_LOGGER,
    DriverSocketAddressFilter,
)
from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import (
    DriverDemand,
    Realtime,
    build_alert_expiry,
    build_alert_snapshots,
    build_alert_use_cases,
    build_driver_demand,
    build_driver_use_cases,
    build_realtime,
    build_stop_use_cases,
)
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from tests.support.alerts_app import DEVICE, OTHER_DEVICE, body_for, headers
from tests.support.driver_app import DRIVER_API, IssuedCode, bearer, issue_code
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.sae import STOP_508_PEAK
from tests.support.stops import (
    API,
    import_feed,
    new_engine,
    replay,
    simulated_sensor,
    stops_settings,
    token,
)
from tests.support.ws import FakeSleep, receive_json_soon, wait_until_closed

PEAK_START = datetime(2026, 11, 2, 19, 42, 23, 769219, tzinfo=UTC)
ENDPOINT = "/ws/driver"
PASSENGER = "/ws/passenger"
SESSIONS = f"{DRIVER_API}/sessions"
CURRENT = f"{SESSIONS}/current"
VIEW = f"{CURRENT}/view"
TRIP = "93_994_561_488_2271_2_122"
NEXT_TRIP = "93_994_561_488_2271_2_123"
STOP = "508"
STOP_SEQUENCE = 7


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("driver_demand") / "avisabus.sqlite"
    engine = new_engine(path)
    import_feed(engine, GTFS_MINI)
    engine.dispose()
    return path


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(PEAK_START)


@dataclass
class Demand:
    client: TestClient
    engine: Engine
    clock: FakeClock
    realtime: Realtime
    demand: DriverDemand
    expiry: Any

    def tick(self) -> None:
        self.clock.advance(timedelta(seconds=2))

    def code(self, label: str = "Tablet") -> IssuedCode:
        return issue_code(self.engine, self.clock, label)

    def login(self, code: IssuedCode | None = None) -> str:
        response = self.client.post(SESSIONS, json={"code": (code or self.code()).plain})
        assert response.status_code == 201, response.text
        token_value: str = response.json()["session_token"]
        return token_value

    def select(self, session_token: str, trip_id: str = TRIP) -> None:
        self.tick()
        response = self.client.put(
            f"{CURRENT}/service",
            json={
                "line": "93",
                "direction_id": 0,
                "trip_id": trip_id,
                "service_date": "2026-11-02",
            },
            headers=bearer(session_token),
        )
        assert response.status_code == 200, response.text

    def move_to_stop(self, session_token: str, sequence: int = 4, trip_id: str = TRIP) -> None:
        """Put the bus at a stop of its trip: the next five stops include the 508 (sequence 7)."""
        network = SqliteNetworkRepository(self.engine)
        call = next(s for s in network.trip_stop_times(trip_id) if s.stop_sequence == sequence)
        stop = network.get_stop(call.stop_id)
        assert stop is not None
        self.tick()
        response = self.client.put(
            f"{CURRENT}/position",
            json={
                "lat": stop.lat,
                "lon": stop.lon,
                "accuracy_m": 5.0,
                "recorded_at": self.clock.now().isoformat(),
            },
            headers=bearer(session_token),
        )
        assert response.status_code == 204, response.text

    def request_stop(
        self, needs: list[str] | None = None, device: str = DEVICE, trip_id: str = TRIP
    ) -> dict[str, Any]:
        arrivals = self.client.get(f"{API}/stops/{STOP}/arrivals", params={"t": token(STOP)})
        arrival = next(a for a in arrivals.json()["arrivals"] if a["vehicle"]["trip_id"] == trip_id)
        self.tick()
        response = self.client.post(
            f"{API}/alerts",
            json=body_for(arrival, STOP, token(STOP), needs=needs or []),
            headers=headers(device),
        )
        assert response.status_code == 201, response.text
        alert: dict[str, Any] = response.json()
        return alert

    def cancel(self, alert_id: str, device: str = DEVICE) -> None:
        self.tick()
        response = self.client.delete(f"{API}/alerts/{alert_id}", headers=headers(device))
        assert response.status_code == 204, response.text


@contextmanager
def _running(
    mini_feed: Path, tmp_path: Path, clock: FakeClock, sleep: FakeSleep | None = None
) -> Iterator[Demand]:
    path = tmp_path / "avisabus.sqlite"
    path.write_bytes(mini_feed.read_bytes())
    engine = new_engine(path)
    source, _ = replay(STOP_508_PEAK, clock, start=PEAK_START)
    settings = stops_settings()
    sleep = sleep or FakeSleep()
    sensor = simulated_sensor(settings, engine, clock)
    stops = build_stop_use_cases(settings, engine, clock, source, sensor, {})
    realtime = build_realtime(settings, clock, snapshots=build_alert_snapshots(engine), sleep=sleep)
    demand = build_driver_demand(settings, engine, clock, sensor, realtime, sleep=sleep)
    alerts = build_alert_use_cases(settings, engine, clock, stops, realtime.publisher, demand)
    expiry = build_alert_expiry(settings, engine, clock, stops, realtime.publisher, demand)
    drivers = build_driver_use_cases(settings, engine, clock, listener=demand.listener)
    app = create_app(
        settings, stops=stops, realtime=realtime, alerts=alerts, drivers=drivers, demand=demand
    )
    with TestClient(app) as client:
        yield Demand(client, engine, clock, realtime, demand, expiry)
    engine.dispose()


@pytest.fixture
def app(mini_feed: Path, tmp_path: Path, clock: FakeClock) -> Iterator[Demand]:
    with _running(mini_feed, tmp_path, clock) as built:
        yield built


def _hello(ws: WebSocketTestSession, session_token: str) -> dict[str, Any]:
    ws.send_json({"type": "hello", "session_token": session_token})
    view: dict[str, Any] = receive_json_soon(ws)
    assert view["type"] == "driver.view"
    return view


def _passenger(ws: WebSocketTestSession, device: str = DEVICE) -> None:
    ws.send_json({"type": "hello", "device_id": device})
    assert receive_json_soon(ws)["type"] == "alerts.snapshot"


def _stop_of(view: dict[str, Any]) -> dict[str, Any]:
    return next(s for s in view["stops"] if s["stop_sequence"] == STOP_SEQUENCE)


def _assert_closed(ws: WebSocketTestSession, code: int) -> None:
    with pytest.raises(WebSocketDisconnect) as closed:
        receive_json_soon(ws)
    assert closed.value.code == code


@pytest.mark.spec("driver_demand.AC-08")
def test_a_valid_hello_gets_the_current_view(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)

    with app.client.websocket_connect(ENDPOINT) as ws:
        view = _hello(ws, session_token)

    assert view["service"]["trip_id"] == TRIP
    assert view["gps"] == "WAITING"


@pytest.mark.spec("driver_demand.AC-07")
def test_a_shift_without_a_departure_gets_a_view_without_a_service(app: Demand) -> None:
    with app.client.websocket_connect(ENDPOINT) as ws:
        view = _hello(ws, app.login())

    assert view["service"] is None
    assert view["stops"] == []
    assert view["capacity_alert"] is False


@pytest.mark.spec("driver_demand.AC-08")
def test_no_hello_in_time_closes_with_4408(
    mini_feed: Path, tmp_path: Path, clock: FakeClock
) -> None:
    with (
        _running(mini_feed, tmp_path, clock, FakeSleep({5.0: 1})) as built,
        built.client.websocket_connect(ENDPOINT) as ws,
    ):
        _assert_closed(ws, 4408)


@pytest.mark.spec("driver_demand.AC-08")
def test_the_hello_waits_for_the_configured_five_seconds(
    mini_feed: Path, tmp_path: Path, clock: FakeClock
) -> None:
    sleep = FakeSleep()
    with (
        _running(mini_feed, tmp_path, clock, sleep) as built,
        built.client.websocket_connect(ENDPOINT) as ws,
    ):
        ws.send_json({"type": "hello", "session_token": built.login()})
        assert receive_json_soon(ws)["type"] == "driver.view"
    assert 5.0 in sleep.calls
    assert 25.0 in sleep.calls


@pytest.mark.spec("driver_demand.AC-08")
@pytest.mark.parametrize(
    "session_token", ["", "not-a-token", "\ud800"], ids=["empty", "unknown", "lone-surrogate"]
)
def test_a_token_of_no_open_shift_closes_with_4401(app: Demand, session_token: str) -> None:
    with app.client.websocket_connect(ENDPOINT) as ws:
        ws.send_json({"type": "hello", "session_token": session_token})
        _assert_closed(ws, 4401)


@pytest.mark.spec("driver_demand.AC-08")
def test_the_token_of_a_closed_shift_closes_with_4401(app: Demand) -> None:
    session_token = app.login()
    assert app.client.delete(CURRENT, headers=bearer(session_token)).status_code == 204

    with app.client.websocket_connect(ENDPOINT) as ws:
        ws.send_json({"type": "hello", "session_token": session_token})
        _assert_closed(ws, 4401)


@pytest.mark.spec("driver_demand.AC-08")
@pytest.mark.parametrize(
    "message",
    [
        '{"type": "hello"}',
        '{"type": "hello", "session_token": 7}',
        '{"type": "other", "session_token": "x"}',
        '["hello"]',
        "not json",
    ],
)
def test_a_malformed_hello_closes_with_4400(app: Demand, message: str) -> None:
    with app.client.websocket_connect(ENDPOINT) as ws:
        ws.send_text(message)
        _assert_closed(ws, 4400)


@pytest.mark.spec("driver_demand.AC-08")
def test_a_binary_hello_closes_with_4400(app: Demand) -> None:
    with app.client.websocket_connect(ENDPOINT) as ws:
        ws.send_bytes(b"hello")
        _assert_closed(ws, 4400)


@pytest.mark.spec("driver_demand.AC-08")
def test_pings_are_sent_periodically(mini_feed: Path, tmp_path: Path, clock: FakeClock) -> None:
    with (
        _running(mini_feed, tmp_path, clock, FakeSleep({25.0: 1})) as built,
        built.client.websocket_connect(ENDPOINT) as ws,
    ):
        _hello(ws, built.login())
        assert receive_json_soon(ws) == {"type": "ping"}


@pytest.mark.spec("driver_demand.AC-08")
def test_the_socket_gets_every_new_view_and_ignores_client_messages(app: Demand) -> None:
    session_token = app.login()
    with app.client.websocket_connect(ENDPOINT) as ws:
        _hello(ws, session_token)
        ws.send_json({"type": "pong"})
        app.select(session_token)
        assert receive_json_soon(ws)["service"]["trip_id"] == TRIP
        app.move_to_stop(session_token)
        assert receive_json_soon(ws)["gps"] == "OK"


@pytest.mark.spec("driver_demand.AC-08")
def test_views_only_reach_the_socket_of_their_own_shift(app: Demand) -> None:
    mine, theirs = app.login(), app.login()
    with (
        app.client.websocket_connect(ENDPOINT) as ws_mine,
        app.client.websocket_connect(ENDPOINT) as ws_theirs,
    ):
        _hello(ws_mine, mine)
        _hello(ws_theirs, theirs)
        app.select(mine)
        assert receive_json_soon(ws_mine)["service"]["trip_id"] == TRIP
        with pytest.raises(AssertionError, match="sent nothing"):
            receive_json_soon(ws_theirs, turns=50)


@pytest.mark.spec("driver_demand.AC-08")
def test_the_socket_counts_against_the_connection_limit(
    mini_feed: Path, tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AVISABUS_WS_MAX_CONNECTIONS", "1")
    with (
        _running(mini_feed, tmp_path, clock) as built,
        built.client.websocket_connect(PASSENGER) as first,
        built.client.websocket_connect(ENDPOINT) as second,
    ):
        _passenger(first)
        _assert_closed(second, 1013)


@pytest.mark.spec("driver_demand.AC-01")
def test_a_request_for_a_bus_with_a_driver_is_delivered_and_shown(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    app.move_to_stop(session_token)
    with (
        app.client.websocket_connect(ENDPOINT) as driver,
        app.client.websocket_connect(PASSENGER) as passenger,
    ):
        _hello(driver, session_token)
        _passenger(passenger)

        alert = app.request_stop(["RAMP", "SEAT"])

        assert alert["status"] == "DELIVERED"
        assert receive_json_soon(passenger) == {"type": "alert.delivered", "alert": alert}
        view = receive_json_soon(driver)
    stop = _stop_of(view)
    assert stop["stop_id"] == STOP
    assert stop["waiting"] == 1
    assert stop["needs"] == {"RAMP": 1, "EXTRA_TIME": 0, "SEAT": 1, "VISUAL": 0}
    assert stop["alert_ids"] == [alert["alert_id"]]
    assert view["total_waiting"] == 1


@pytest.mark.spec("driver_demand.AC-05")
def test_the_view_carries_no_data_of_the_device(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    app.move_to_stop(session_token)
    with app.client.websocket_connect(ENDPOINT) as driver:
        _hello(driver, session_token)
        app.request_stop(["RAMP"])
        text = repr(receive_json_soon(driver))

    assert DEVICE not in text
    assert "device" not in text


@pytest.mark.spec("driver_demand.AC-01")
def test_a_request_for_another_bus_stays_pending(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token, NEXT_TRIP)

    alert = app.request_stop()

    assert alert["status"] == "PENDING_DRIVER"


@pytest.mark.spec("driver_demand.AC-02")
def test_choosing_a_departure_delivers_its_pending_requests(app: Demand) -> None:
    alert = app.request_stop(["SEAT"])
    assert alert["status"] == "PENDING_DRIVER"
    session_token = app.login()
    with (
        app.client.websocket_connect(ENDPOINT) as driver,
        app.client.websocket_connect(PASSENGER) as passenger,
    ):
        _hello(driver, session_token)
        _passenger(passenger)

        app.select(session_token)

        event = receive_json_soon(passenger)
        assert event["type"] == "alert.delivered"
        assert event["alert"] == {**alert, "status": "DELIVERED"}
        assert receive_json_soon(driver)["service"]["trip_id"] == TRIP
        app.move_to_stop(session_token)
        assert _stop_of(receive_json_soon(driver))["waiting"] == 1


@pytest.mark.spec("driver_demand.AC-02")
def test_changing_departure_returns_the_requests_of_the_old_one(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    alert = app.request_stop()
    assert alert["status"] == "DELIVERED"
    with (
        app.client.websocket_connect(ENDPOINT) as driver,
        app.client.websocket_connect(PASSENGER) as passenger,
    ):
        _hello(driver, session_token)
        _passenger(passenger)

        app.select(session_token, NEXT_TRIP)

        assert receive_json_soon(passenger) == {
            "type": "alert.registered",
            "alert": {**alert, "status": "PENDING_DRIVER"},
        }
        view = receive_json_soon(driver)
    assert view["service"]["trip_id"] == NEXT_TRIP
    assert view["total_waiting"] == 0
    mine = app.client.get(f"{API}/alerts/mine", headers=headers()).json()
    assert mine["alerts"][0]["status"] == "PENDING_DRIVER"


@pytest.mark.spec("driver_demand.AC-03")
def test_ending_a_shift_returns_requests_and_closes_the_socket_after_telling_it(
    app: Demand,
) -> None:
    session_token = app.login()
    app.select(session_token)
    alert = app.request_stop()
    with (
        app.client.websocket_connect(ENDPOINT) as driver,
        app.client.websocket_connect(PASSENGER) as passenger,
    ):
        _hello(driver, session_token)
        _passenger(passenger)

        assert app.client.delete(CURRENT, headers=bearer(session_token)).status_code == 204

        assert receive_json_soon(passenger) == {
            "type": "alert.registered",
            "alert": {**alert, "status": "PENDING_DRIVER"},
        }
        assert receive_json_soon(driver) == {"type": "session.closed", "reason": "ENDED"}
        _assert_closed(driver, 1000)


@pytest.mark.spec("driver_demand.AC-03")
def test_a_new_login_with_the_same_code_replaces_the_shift(app: Demand) -> None:
    code = app.code()
    session_token = app.login(code)
    with app.client.websocket_connect(ENDPOINT) as driver:
        _hello(driver, session_token)

        app.login(code)

        assert receive_json_soon(driver) == {"type": "session.closed", "reason": "REPLACED"}
        _assert_closed(driver, 1000)


@pytest.mark.spec("driver_demand.AC-03")
def test_the_socket_is_released_when_the_client_leaves(app: Demand) -> None:
    session_token = app.login()
    with app.client.websocket_connect(ENDPOINT) as driver:
        _hello(driver, session_token)
        assert app.realtime.publisher.subscriber_count() == 1
    wait_until_closed(app.client, app.realtime.registry)
    assert app.realtime.publisher.subscriber_count() == 0


@pytest.mark.spec("driver_demand.AC-04")
def test_cancelling_a_delivered_request_publishes_a_new_view(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    app.move_to_stop(session_token)
    alert = app.request_stop()
    with app.client.websocket_connect(ENDPOINT) as driver:
        assert _stop_of(_hello(driver, session_token))["waiting"] == 1

        app.cancel(alert["alert_id"])

        view = receive_json_soon(driver)
    assert _stop_of(view)["waiting"] == 0
    assert view["total_waiting"] == 0


@pytest.mark.spec("driver_demand.AC-04")
def test_an_expired_delivered_request_publishes_a_new_view(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    app.move_to_stop(session_token)
    alert = app.request_stop()
    with app.client.websocket_connect(ENDPOINT) as driver:
        assert _stop_of(_hello(driver, session_token))["waiting"] == 1

        app.clock.advance(timedelta(minutes=31))
        assert app.client.portal is not None
        app.client.portal.call(app.expiry.expire_due_alerts.tick)

        view = receive_json_soon(driver)
    assert _stop_of(view)["waiting"] == 0
    assert app.client.get(f"{API}/alerts/mine", headers=headers()).json() == {"alerts": []}
    assert alert["status"] == "DELIVERED"


@pytest.mark.spec("driver_demand.AC-09")
def test_a_new_view_reaches_the_driver_when_the_gps_comes_back(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    app.move_to_stop(session_token)
    with app.client.websocket_connect(ENDPOINT) as driver:
        assert _hello(driver, session_token)["gps"] == "OK"

        app.clock.advance(timedelta(seconds=31))
        assert app.client.portal is not None
        app.client.portal.call(app.demand.views.refresh_all)
        assert receive_json_soon(driver)["gps"] == "STALE"

        app.move_to_stop(session_token, sequence=4)
        assert receive_json_soon(driver)["gps"] == "OK"


@pytest.mark.spec("driver_demand.AC-10")
def test_the_view_endpoint_answers_the_same_view_as_the_socket(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    app.move_to_stop(session_token)
    app.request_stop(["RAMP"])

    response = app.client.get(VIEW, headers=bearer(session_token))
    with app.client.websocket_connect(ENDPOINT) as driver:
        message = _hello(driver, session_token)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    expected = {key: value for key, value in message.items() if key != "type"}
    assert response.json() == expected
    assert response.json()["service"]["departure_at"] == "2026-11-02T19:42:00Z"
    assert expected["total_waiting"] == 1


@pytest.mark.spec("driver_demand.AC-10")
def test_the_view_endpoint_requires_an_open_shift(app: Demand) -> None:
    assert app.client.get(VIEW).status_code == 401
    assert app.client.get(VIEW, headers=bearer("nope")).status_code == 401


@pytest.mark.spec("driver_demand.AC-11")
def test_creating_and_cancelling_reach_the_driver_within_five_seconds(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    app.move_to_stop(session_token)
    with app.client.websocket_connect(ENDPOINT) as driver:
        _hello(driver, session_token)

        alert = app.request_stop()
        created = datetime.fromisoformat(alert["created_at"])
        shown = receive_json_soon(driver)  # bounded in loop turns: no real time passes
        assert datetime.fromisoformat(shown["generated_at"]) - created <= timedelta(seconds=5)
        assert shown["total_waiting"] == 1

        cancelled_at = app.clock.now() + timedelta(seconds=2)
        app.cancel(alert["alert_id"])
        gone = receive_json_soon(driver)
        assert datetime.fromisoformat(gone["generated_at"]) - cancelled_at <= timedelta(seconds=5)
        assert gone["total_waiting"] == 0


@pytest.mark.spec("driver_demand.AC-12")
def test_the_logs_of_a_delivery_carry_no_needs_nor_device(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    with capture_logs() as logs, app.client.websocket_connect(ENDPOINT) as driver:
        _hello(driver, session_token)
        alert = app.request_stop(["RAMP", "SEAT"])
        receive_json_soon(driver)
        app.select(session_token, NEXT_TRIP)
        receive_json_soon(driver)

    delivered = [e for e in logs if e["event"] == "alert.delivered"]
    undelivered = [e for e in logs if e["event"] == "alert.undelivered"]
    assert [e["alert_id"] for e in delivered] == [alert["alert_id"]]
    assert [e["alert_id"] for e in undelivered] == [alert["alert_id"]]
    assert undelivered[0]["reason"] == "SERVICE_CHANGED"
    assert delivered[0]["session_id"] == undelivered[0]["session_id"]
    for entry in [*delivered, *undelivered]:
        assert set(entry) <= {"event", "log_level", "alert_id", "session_id", "reason"}
    text = repr(logs)
    assert DEVICE not in text
    assert session_token not in text
    assert "driver.view" not in text
    assert "total_waiting" not in text


@pytest.mark.spec("driver_demand.AC-12")
def test_the_logs_of_the_socket_identify_neither_the_shift_nor_the_token(app: Demand) -> None:
    session_token = app.login()
    with capture_logs() as logs, app.client.websocket_connect(ENDPOINT) as driver:
        _hello(driver, session_token)
    wait_until_closed(app.client, app.realtime.registry)

    sockets = [e for e in logs if e["event"] in {"ws.connected", "ws.closed"}]
    assert {e["event"] for e in sockets} == {"ws.connected", "ws.closed"}
    for entry in sockets:
        assert entry["endpoint"] == ENDPOINT
        assert "session_id" not in entry
    assert session_token not in repr(logs)


@pytest.mark.spec("driver_demand.AC-12")
def test_a_failing_socket_only_logs_the_type_of_the_exception(
    app: Demand, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_token = app.login()

    async def explode(_session: object) -> None:
        raise RuntimeError(f"secret {session_token}")

    monkeypatch.setattr(app.demand.build_view, "execute", explode)
    with capture_logs() as logs, app.client.websocket_connect(ENDPOINT) as ws:
        ws.send_json({"type": "hello", "session_token": session_token})
        _assert_closed(ws, 1011)

    failures = [e for e in logs if e["event"] == "unhandled_exception"]
    assert failures[0]["error_type"] == "RuntimeError"
    assert session_token not in repr(logs)


UVICORN_FORMATS = ['%s - "WebSocket %s" [accepted]', '%s - "WebSocket %s" 403']


def _emit(message: str, *args: object) -> str:
    """What the uvicorn server logger writes, after the filters installed by `create_app`."""
    logger = logging.getLogger(SERVER_LOGGER)
    record = logger.makeRecord(SERVER_LOGGER, logging.INFO, __file__, 1, message, args, None)
    assert logger.filter(record)
    return record.getMessage()


@pytest.mark.spec("driver_demand.AC-12")
@pytest.mark.parametrize("message", UVICORN_FORMATS)
def test_the_server_log_of_the_driver_socket_has_no_address(app: Demand, message: str) -> None:
    written = _emit(message, "203.0.113.7:50000", ENDPOINT)

    assert "203.0.113.7" not in written
    assert ENDPOINT in written


@pytest.mark.spec("driver_demand.AC-12")
def test_the_server_log_of_the_driver_socket_drops_the_query_string(app: Demand) -> None:
    written = _emit(UVICORN_FORMATS[0], "203.0.113.7:50000", f"{ENDPOINT}?session_token=abc")

    assert "abc" not in written
    assert "203.0.113.7" not in written


@pytest.mark.spec("driver_demand.AC-12")
def test_a_status_after_the_path_is_kept(app: Demand) -> None:
    written = _emit('%s - "WebSocket %s" %d', "203.0.113.7:50000", ENDPOINT, 500)

    assert written == f'- - "WebSocket {ENDPOINT}" 500'


def test_other_server_logs_are_left_as_they_were(app: Demand) -> None:
    assert (
        _emit(UVICORN_FORMATS[0], "203.0.113.7:50000", PASSENGER)
        == f'203.0.113.7:50000 - "WebSocket {PASSENGER}" [accepted]'
    )
    assert _emit("Started server process [%d]", 12) == "Started server process [12]"


def test_the_filter_is_installed_only_once(app: Demand) -> None:
    create_app(stops_settings(), demand=app.demand, drivers=None)
    logger = logging.getLogger(SERVER_LOGGER)

    assert sum(isinstance(f, DriverSocketAddressFilter) for f in logger.filters) == 1


def test_two_devices_and_one_shift_share_the_demand_of_the_stop(app: Demand) -> None:
    session_token = app.login()
    app.select(session_token)
    app.move_to_stop(session_token)
    app.request_stop(["RAMP"])
    app.request_stop(["RAMP", "VISUAL"], device=OTHER_DEVICE)

    view = app.client.get(VIEW, headers=bearer(session_token)).json()

    assert _stop_of(view)["needs"] == {"RAMP": 2, "EXTRA_TIME": 0, "SEAT": 0, "VISUAL": 1}
    assert _stop_of(view)["waiting"] == 2
