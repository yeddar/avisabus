"""`/api/v1/driver` over `gtfs_mini` with a FakeClock (driver_session T-05).

The codes are created with the real use case. The positions are real points of the shape of the
chosen trip.
"""

import hashlib
import logging
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import Engine, text
from structlog.testing import capture_logs

from avisabus.adapters.inbound.http.access_log import ACCESS_LOGGER, DriverAddressFilter
from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.outbound.persistence.sqlite_driver_sessions import (
    SqliteDriverSessionRepository,
)
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.domain.models.driver import DriverService, SessionCloseReason
from avisabus.domain.models.network import ShapePoint
from tests.support.driver_app import (
    DRIVER_API,
    PROBLEM_BASE,
    PROBLEM_JSON,
    IssuedCode,
    bearer,
    driver_client,
    driver_use_cases,
    issue_code,
    login,
    revoke_code,
)
from tests.support.drivers import RecordingListener, session_of
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.stops import import_feed, new_engine, stops_settings

NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)  # Monday, 09:00 in Madrid
SESSIONS = f"{DRIVER_API}/sessions"
CURRENT = f"{SESSIONS}/current"
SERVICE = f"{CURRENT}/service"
POSITION = f"{CURRENT}/position"
LINES = f"{DRIVER_API}/lines"
DEPARTURES = f"{DRIVER_API}/departures"
INVALID_CODE = f"{PROBLEM_BASE}/invalid-driver-code"
INVALID_SESSION = f"{PROBLEM_BASE}/invalid-session"
INVALID_DEPARTURE = f"{PROBLEM_BASE}/invalid-departure"
DEPARTURE_TAKEN = f"{PROBLEM_BASE}/departure-taken"
RATE_LIMITED = f"{PROBLEM_BASE}/rate-limited"
NETWORK_UNAVAILABLE = f"{PROBLEM_BASE}/network-unavailable"
_ACCESS_FORMAT = '%s - "%s %s HTTP/%s" %d'
GOOD_POSITION = {
    "lat": 39.47,
    "lon": -0.37,
    "accuracy_m": 8.5,
    "recorded_at": NOW.isoformat(),
}


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("driver") / "avisabus.sqlite"
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


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock(NOW)


@pytest.fixture
def listener() -> RecordingListener:
    return RecordingListener()


@pytest.fixture
async def client(
    engine: Engine, clock: FakeClock, listener: RecordingListener
) -> AsyncIterator[httpx.AsyncClient]:
    async with driver_client(driver_use_cases(engine, clock, listener)) as http:
        yield http


@pytest.fixture
def code(engine: Engine, clock: FakeClock) -> IssuedCode:
    return issue_code(engine, clock)


@pytest.fixture
async def auth(client: httpx.AsyncClient, code: IssuedCode) -> dict[str, str]:
    return bearer((await login(client, code))["session_token"])


async def _first_departure(
    client: httpx.AsyncClient, auth: dict[str, str], line: str = "93", direction_id: int = 0
) -> dict[str, Any]:
    response = await client.get(
        DEPARTURES, params={"line": line, "direction_id": direction_id}, headers=auth
    )
    assert response.status_code == 200
    departure: dict[str, Any] = response.json()["departures"][0]
    return departure


def _service_of(departure: dict[str, Any], line: str = "93", direction: int = 0) -> dict[str, Any]:
    return {
        "line": line,
        "direction_id": direction,
        "trip_id": departure["trip_id"],
        "service_date": departure["service_date"],
    }


async def _take_first_departure(client: httpx.AsyncClient, auth: dict[str, str]) -> dict[str, Any]:
    departure = await _first_departure(client, auth)
    response = await client.put(SERVICE, json=_service_of(departure), headers=auth)
    assert response.status_code == 200, response.text
    return departure


def _shape_of(engine: Engine, trip_id: str) -> list[ShapePoint]:
    network = SqliteNetworkRepository(engine)
    shape_id = network.trip_shape_id(trip_id)
    assert shape_id is not None
    return network.shape_points(shape_id)


def _position_at(point: ShapePoint, recorded_at: datetime) -> dict[str, Any]:
    return {
        "lat": point.lat,
        "lon": point.lon,
        "accuracy_m": 5.0,
        "recorded_at": recorded_at.isoformat(),
    }


def _rows(engine: Engine) -> list[dict[str, Any]]:
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text("SELECT * FROM driver_session")).mappings()]


def _assert_problem(response: httpx.Response, status: int, problem_type: str) -> None:
    assert response.status_code == status
    assert response.headers["content-type"] == PROBLEM_JSON
    assert response.json()["type"] == problem_type


# --- AC-01 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-01")
async def test_login_creates_a_session(
    client: httpx.AsyncClient, code: IssuedCode, engine: Engine
) -> None:
    response = await client.post(SESSIONS, json={"code": code.plain})
    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"session_id", "session_token", "idle_timeout_s"}
    assert body["idle_timeout_s"] == 600
    assert len(body["session_token"]) >= 43
    row = _rows(engine)[0]
    assert row["session_id"] == body["session_id"]
    assert row["code_id"] == code.code_id
    assert row["token_hash"] == hashlib.sha256(body["session_token"].encode()).hexdigest()
    assert body["session_token"] not in repr(row)


@pytest.mark.spec("driver_session.AC-01")
async def test_login_ignores_spaces_in_the_code(
    client: httpx.AsyncClient, code: IssuedCode
) -> None:
    spaced = f"{code.plain[:4]} {code.plain[4:]}"
    response = await client.post(SESSIONS, json={"code": spaced})
    assert response.status_code == 201


@pytest.mark.spec("driver_session.AC-01")
@pytest.mark.parametrize("body", [{}, {"code": 48210937}, {"other": "x"}])
async def test_login_with_a_malformed_body_is_rejected(
    client: httpx.AsyncClient, body: dict[str, Any]
) -> None:
    response = await client.post(SESSIONS, json=body)
    assert response.status_code == 422


# --- AC-02 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-02")
async def test_unknown_and_revoked_codes_have_the_same_answer(
    client: httpx.AsyncClient, code: IssuedCode, engine: Engine, clock: FakeClock
) -> None:
    unknown = await client.post(SESSIONS, json={"code": "00000000"})
    revoke_code(engine, clock, code.code_id)
    revoked = await client.post(SESSIONS, json={"code": code.plain})
    _assert_problem(unknown, 401, INVALID_CODE)
    _assert_problem(revoked, 401, INVALID_CODE)
    assert unknown.content == revoked.content
    assert _rows(engine) == []


@pytest.mark.spec("driver_session.AC-02")
async def test_a_malformed_code_is_an_invalid_code(client: httpx.AsyncClient) -> None:
    _assert_problem(await client.post(SESSIONS, json={"code": "abc"}), 401, INVALID_CODE)


@pytest.mark.spec("driver_session.AC-02")
async def test_five_failures_block_the_address_even_with_a_valid_code(
    client: httpx.AsyncClient, code: IssuedCode, clock: FakeClock
) -> None:
    for _ in range(5):
        _assert_problem(await client.post(SESSIONS, json={"code": "00000000"}), 401, INVALID_CODE)
    clock.advance(timedelta(minutes=1))
    blocked = await client.post(SESSIONS, json={"code": code.plain})
    _assert_problem(blocked, 429, RATE_LIMITED)
    assert blocked.headers["retry-after"] == str(14 * 60)


@pytest.mark.spec("driver_session.AC-02")
async def test_the_block_ends_15_minutes_after_the_last_failure(
    client: httpx.AsyncClient, code: IssuedCode, clock: FakeClock
) -> None:
    for _ in range(5):
        await client.post(SESSIONS, json={"code": "00000000"})
    clock.advance(timedelta(minutes=15))
    assert (await client.post(SESSIONS, json={"code": code.plain})).status_code == 201


# --- AC-03 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-03")
async def test_a_second_login_with_the_same_code_replaces_the_shift(
    client: httpx.AsyncClient,
    code: IssuedCode,
    engine: Engine,
    listener: RecordingListener,
) -> None:
    first = await login(client, code)
    second = await login(client, code)
    assert [row["session_id"] for row in _rows(engine)] == [second["session_id"]]
    old_session = await client.get(CURRENT, headers=bearer(first["session_token"]))
    _assert_problem(old_session, 401, INVALID_SESSION)
    assert (await client.get(CURRENT, headers=bearer(second["session_token"]))).status_code == 200
    assert listener.calls == [("session_closed", first["session_id"], SessionCloseReason.REPLACED)]


# --- AC-04 ---------------------------------------------------------------------------------

_PROTECTED = [
    ("GET", LINES, None),
    ("GET", f"{DEPARTURES}?line=93&direction_id=0", None),
    ("GET", CURRENT, None),
    ("DELETE", CURRENT, None),
    ("PUT", POSITION, GOOD_POSITION),
    (
        "PUT",
        SERVICE,
        {"line": "93", "direction_id": 0, "trip_id": "t", "service_date": "2026-11-09"},
    ),
]


@pytest.mark.spec("driver_session.AC-04")
@pytest.mark.parametrize(("method", "url", "body"), _PROTECTED)
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-real-token"},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer "},
    ],
)
async def test_endpoints_require_a_valid_token(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    body: dict[str, Any] | None,
    headers: dict[str, str],
) -> None:
    response = await client.request(method, url, json=body, headers=headers)
    _assert_problem(response, 401, INVALID_SESSION)


@pytest.mark.spec("driver_session.AC-04")
async def test_the_scheme_of_the_token_is_case_insensitive(
    client: httpx.AsyncClient, code: IssuedCode
) -> None:
    token = (await login(client, code))["session_token"]
    response = await client.get(CURRENT, headers={"Authorization": f"bearer {token}"})
    assert response.status_code == 200


@pytest.mark.spec("driver_session.AC-04")
async def test_a_closed_session_is_no_longer_valid(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    assert (await client.delete(CURRENT, headers=auth)).status_code == 204
    _assert_problem(await client.get(CURRENT, headers=auth), 401, INVALID_SESSION)


# --- AC-05 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-05")
async def test_lines_are_in_line_order_with_colours_and_directions(
    client: httpx.AsyncClient, auth: dict[str, str], engine: Engine
) -> None:
    response = await client.get(LINES, headers=auth)
    assert response.status_code == 200
    lines = response.json()["lines"]
    assert [item["line"] for item in lines] == ["70", "93", "98", "C2"]
    network = SqliteNetworkRepository(engine)
    for item in lines:
        line = network.get_line(item["line"])
        assert line is not None
        assert (item["color"], item["text_color"]) == (line.color, line.text_color)
        assert item["directions"] == [
            {"direction_id": d.direction_id, "headsign": d.headsign}
            for d in network.line_directions(item["line"])
        ]


# --- AC-06 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-06")
async def test_departures_are_those_of_the_window_in_time_order(
    client: httpx.AsyncClient, auth: dict[str, str], clock: FakeClock
) -> None:
    response = await client.get(DEPARTURES, params={"line": "93", "direction_id": 0}, headers=auth)
    assert response.status_code == 200
    departures = response.json()["departures"]
    assert departures
    instants = [datetime.fromisoformat(d["departure_at"]) for d in departures]
    assert instants == sorted(instants)
    assert all(
        NOW - timedelta(minutes=30) <= instant <= NOW + timedelta(minutes=60)
        for instant in instants
    )
    assert set(departures[0]) == {
        "trip_id",
        "service_date",
        "departure_at",
        "first_stop_name",
        "headsign",
        "taken",
    }
    assert departures[0]["service_date"] == "2026-11-09"
    assert departures[0]["taken"] is False
    assert departures[0]["first_stop_name"]


@pytest.mark.spec("driver_session.AC-06")
async def test_a_departure_held_by_another_shift_is_marked_as_taken(
    client: httpx.AsyncClient, auth: dict[str, str], engine: Engine
) -> None:
    departure = await _first_departure(client, auth)
    SqliteDriverSessionRepository(engine).add(
        session_of(
            2,
            DriverService(
                "93",
                0,
                departure["trip_id"],
                datetime.fromisoformat(departure["service_date"]).date(),
            ),
        )
    )
    assert (await _first_departure(client, auth))["taken"] is True


@pytest.mark.spec("driver_session.AC-06")
async def test_the_own_departure_is_not_taken(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    await _take_first_departure(client, auth)
    assert (await _first_departure(client, auth))["taken"] is False


@pytest.mark.spec("driver_session.AC-06")
async def test_departures_includes_trips_past_midnight_of_the_previous_service_day(
    client: httpx.AsyncClient, auth: dict[str, str], clock: FakeClock
) -> None:
    clock.set(datetime(2026, 11, 9, 23, 30, tzinfo=UTC))  # 00:30 of Tuesday in Madrid
    response = await client.get(DEPARTURES, params={"line": "93", "direction_id": 0}, headers=auth)
    assert response.status_code == 200
    assert {d["service_date"] for d in response.json()["departures"]} == {"2026-11-09"}


@pytest.mark.spec("driver_session.AC-06")
async def test_an_unknown_line_has_no_departures(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    response = await client.get(
        DEPARTURES, params={"line": "nope", "direction_id": 0}, headers=auth
    )
    assert response.status_code == 200
    assert response.json() == {"departures": []}


@pytest.mark.spec("driver_session.AC-06")
@pytest.mark.parametrize("params", [{}, {"line": "93"}, {"direction_id": 0}])
async def test_departures_require_line_and_direction(
    client: httpx.AsyncClient, auth: dict[str, str], params: dict[str, Any]
) -> None:
    response = await client.get(DEPARTURES, params=params, headers=auth)
    assert response.status_code == 422


# --- AC-07 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-07")
async def test_selecting_a_departure_answers_the_state_and_notifies(
    client: httpx.AsyncClient,
    auth: dict[str, str],
    listener: RecordingListener,
    engine: Engine,
) -> None:
    departure = await _first_departure(client, auth)
    response = await client.put(SERVICE, json=_service_of(departure), headers=auth)
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == _service_of(departure)
    assert body["gps"] == "WAITING"
    assert _rows(engine)[0]["trip_id"] == departure["trip_id"]
    assert [call[0] for call in listener.calls] == ["service_selected"]


@pytest.mark.spec("driver_session.AC-07")
@pytest.mark.parametrize(
    "change",
    [
        {"trip_id": "not-a-trip"},
        {"line": "70"},
        {"direction_id": 1},
        {"service_date": "2026-11-01"},
    ],
)
async def test_an_invalid_departure_is_rejected(
    client: httpx.AsyncClient,
    auth: dict[str, str],
    engine: Engine,
    change: dict[str, Any],
) -> None:
    departure = await _first_departure(client, auth)
    response = await client.put(SERVICE, json={**_service_of(departure), **change}, headers=auth)
    _assert_problem(response, 422, INVALID_DEPARTURE)
    assert _rows(engine)[0]["trip_id"] is None


@pytest.mark.spec("driver_session.AC-07")
async def test_a_departure_outside_the_window_is_rejected(
    client: httpx.AsyncClient, auth: dict[str, str], clock: FakeClock
) -> None:
    departure = await _first_departure(client, auth)
    clock.advance(timedelta(hours=2))
    response = await client.put(SERVICE, json=_service_of(departure), headers=auth)
    _assert_problem(response, 422, INVALID_DEPARTURE)


@pytest.mark.spec("driver_session.AC-07")
async def test_a_departure_held_by_another_shift_is_refused(
    client: httpx.AsyncClient, auth: dict[str, str], code: IssuedCode, engine: Engine
) -> None:
    departure = await _take_first_departure(client, auth)
    other = issue_code(engine, FakeClock(NOW), "Other")
    token = (await login(client, other))["session_token"]
    response = await client.put(SERVICE, json=_service_of(departure), headers=bearer(token))
    _assert_problem(response, 409, DEPARTURE_TAKEN)


@pytest.mark.spec("driver_session.AC-07")
async def test_the_driver_can_change_departure_during_the_shift(
    client: httpx.AsyncClient,
    auth: dict[str, str],
    engine: Engine,
    listener: RecordingListener,
) -> None:
    first = await _first_departure(client, auth)
    await client.put(SERVICE, json=_service_of(first), headers=auth)
    other = (
        await client.get(DEPARTURES, params={"line": "93", "direction_id": 0}, headers=auth)
    ).json()["departures"][1]
    response = await client.put(SERVICE, json=_service_of(other), headers=auth)
    assert response.status_code == 200
    assert _rows(engine)[0]["trip_id"] == other["trip_id"]
    assert _rows(engine)[0]["progress_m"] is None
    assert listener.calls[1][2] is not None


@pytest.mark.spec("driver_session.AC-07")
async def test_a_body_with_a_bad_date_is_a_validation_error(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    body = {"line": "93", "direction_id": 0, "trip_id": "t", "service_date": "yesterday"}
    response = await client.put(SERVICE, json=body, headers=auth)
    assert response.status_code == 422


# --- AC-08 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-08")
async def test_a_position_is_stored_and_answered_with_204(
    client: httpx.AsyncClient, auth: dict[str, str], engine: Engine
) -> None:
    response = await client.put(POSITION, json=GOOD_POSITION, headers=auth)
    assert response.status_code == 204
    assert response.content == b""
    row = _rows(engine)[0]
    assert (row["lat"], row["lon"], row["accuracy_m"]) == (39.47, -0.37, 8.5)
    assert row["recorded_at"] == NOW.isoformat()


@pytest.mark.spec("driver_session.AC-08")
async def test_an_older_position_is_discarded_with_204(
    client: httpx.AsyncClient, auth: dict[str, str], engine: Engine
) -> None:
    await client.put(POSITION, json=GOOD_POSITION, headers=auth)
    older = {
        **GOOD_POSITION,
        "lat": 10.0,
        "recorded_at": (NOW - timedelta(seconds=1)).isoformat(),
    }
    response = await client.put(POSITION, json=older, headers=auth)
    assert response.status_code == 204
    assert _rows(engine)[0]["lat"] == 39.47


@pytest.mark.spec("driver_session.AC-08")
@pytest.mark.parametrize(
    "change",
    [
        {"lat": 90.1},
        {"lat": -90.1},
        {"lon": 180.1},
        {"lon": -180.1},
        {"accuracy_m": -1},
        {"recorded_at": "2026-11-09T08:00:00"},
        {"recorded_at": "not a date"},
        {"lat": None},
    ],
)
async def test_positions_out_of_range_are_rejected(
    client: httpx.AsyncClient, auth: dict[str, str], engine: Engine, change: dict[str, Any]
) -> None:
    response = await client.put(POSITION, json={**GOOD_POSITION, **change}, headers=auth)
    assert response.status_code == 422
    assert _rows(engine)[0]["recorded_at"] is None


@pytest.mark.spec("driver_session.AC-08")
async def test_coordinates_at_the_limits_are_accepted(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    body = {**GOOD_POSITION, "lat": -90, "lon": 180, "accuracy_m": 0}
    assert (await client.put(POSITION, json=body, headers=auth)).status_code == 204


@pytest.mark.spec("driver_session.AC-08")
async def test_a_position_too_far_in_the_future_is_rejected(
    client: httpx.AsyncClient, auth: dict[str, str], engine: Engine
) -> None:
    body = {**GOOD_POSITION, "recorded_at": (NOW + timedelta(seconds=31)).isoformat()}
    response = await client.put(POSITION, json=body, headers=auth)
    assert response.status_code == 422
    assert _rows(engine)[0]["recorded_at"] is None


@pytest.mark.spec("driver_session.AC-08")
async def test_a_position_30_seconds_ahead_is_accepted(
    client: httpx.AsyncClient, auth: dict[str, str]
) -> None:
    body = {**GOOD_POSITION, "recorded_at": (NOW + timedelta(seconds=30)).isoformat()}
    assert (await client.put(POSITION, json=body, headers=auth)).status_code == 204


# --- AC-11 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-11")
async def test_state_of_a_new_shift(client: httpx.AsyncClient, code: IssuedCode) -> None:
    session = await login(client, code)
    response = await client.get(CURRENT, headers=bearer(session["session_token"]))
    assert response.status_code == 200
    assert response.json() == {
        "session_id": session["session_id"],
        "service": None,
        "gps": "WAITING",
        "off_route": False,
        "finished": False,
        "upcoming": [],
    }


@pytest.mark.spec("driver_session.AC-11")
async def test_state_follows_the_position_along_the_trip(
    client: httpx.AsyncClient, auth: dict[str, str], engine: Engine, clock: FakeClock
) -> None:
    departure = await _take_first_departure(client, auth)
    shape = _shape_of(engine, departure["trip_id"])
    await client.put(POSITION, json=_position_at(shape[len(shape) // 2], NOW), headers=auth)

    body = (await client.get(CURRENT, headers=auth)).json()

    assert body["service"] == _service_of(departure)
    assert body["gps"] == "OK"
    assert body["off_route"] is False
    assert body["finished"] is False
    assert 1 <= len(body["upcoming"]) <= 5
    first = body["upcoming"][0]
    assert set(first) == {"stop_id", "name", "stop_sequence", "distance_m"}
    assert first["distance_m"] > 20
    sequences = [stop["stop_sequence"] for stop in body["upcoming"]]
    assert sequences == sorted(sequences)


@pytest.mark.spec("driver_session.AC-11")
async def test_the_gps_is_stale_after_30_seconds_without_position(
    client: httpx.AsyncClient, auth: dict[str, str], clock: FakeClock
) -> None:
    await client.put(POSITION, json=GOOD_POSITION, headers=auth)
    clock.advance(timedelta(seconds=30))
    assert (await client.get(CURRENT, headers=auth)).json()["gps"] == "OK"
    clock.advance(timedelta(seconds=1))
    assert (await client.get(CURRENT, headers=auth)).json()["gps"] == "STALE"


@pytest.mark.spec("driver_session.AC-11")
async def test_state_reports_off_route(client: httpx.AsyncClient, auth: dict[str, str]) -> None:
    await _take_first_departure(client, auth)
    await client.put(POSITION, json=GOOD_POSITION | {"lat": 10.0}, headers=auth)
    assert (await client.get(CURRENT, headers=auth)).json()["off_route"] is True


@pytest.mark.spec("driver_session.AC-11")
async def test_state_reports_the_end_of_the_trip(
    client: httpx.AsyncClient, auth: dict[str, str], engine: Engine
) -> None:
    departure = await _take_first_departure(client, auth)
    shape = _shape_of(engine, departure["trip_id"])
    await client.put(POSITION, json=_position_at(shape[-1], NOW), headers=auth)
    body = (await client.get(CURRENT, headers=auth)).json()
    assert body["finished"] is True
    assert body["upcoming"] == []


# --- AC-12 ---------------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-12")
async def test_ending_the_shift_deletes_it_with_its_position(
    client: httpx.AsyncClient,
    auth: dict[str, str],
    engine: Engine,
    listener: RecordingListener,
) -> None:
    await client.put(POSITION, json=GOOD_POSITION, headers=auth)
    session_id = _rows(engine)[0]["session_id"]
    response = await client.delete(CURRENT, headers=auth)
    assert response.status_code == 204
    assert _rows(engine) == []
    assert listener.calls[-1] == ("session_closed", session_id, SessionCloseReason.ENDED)


# --- 503, AC-15 ----------------------------------------------------------------------------


@pytest.mark.spec("driver_session.AC-05")
async def test_without_a_feed_the_network_is_unavailable(tmp_path: Path, clock: FakeClock) -> None:
    engine = new_engine(tmp_path / "empty.sqlite")
    try:
        code = issue_code(engine, clock)
        async with driver_client(driver_use_cases(engine, clock)) as http:
            auth = bearer((await login(http, code))["session_token"])
            lines = await http.get(LINES, headers=auth)
            departures = await http.get(
                DEPARTURES, params={"line": "93", "direction_id": 0}, headers=auth
            )
            body = {"line": "93", "direction_id": 0, "trip_id": "t", "service_date": "2026-11-09"}
            service = await http.put(SERVICE, json=body, headers=auth)
    finally:
        engine.dispose()
    _assert_problem(lines, 503, NETWORK_UNAVAILABLE)
    _assert_problem(departures, 503, NETWORK_UNAVAILABLE)
    _assert_problem(service, 503, NETWORK_UNAVAILABLE)


@pytest.mark.spec("driver_session.AC-15")
async def test_every_answer_of_driver_is_no_store(
    client: httpx.AsyncClient, code: IssuedCode
) -> None:
    created = await client.post(SESSIONS, json={"code": code.plain})
    auth = bearer(created.json()["session_token"])
    answers = [
        created,
        await client.get(LINES, headers=auth),
        await client.get(CURRENT, headers=auth),
        await client.put(POSITION, json=GOOD_POSITION, headers=auth),
        await client.delete(CURRENT, headers=auth),
        await client.get(CURRENT),  # 401
        await client.post(SESSIONS, json={}),  # 422 of the validation
        await client.post(SESSIONS, json={"code": "00000000"}),  # 401
    ]
    assert [answer.headers.get("cache-control") for answer in answers] == ["no-store"] * len(
        answers
    )


@pytest.mark.spec("driver_session.AC-15")
async def test_logs_have_no_code_token_coordinates_nor_address(
    client: httpx.AsyncClient, code: IssuedCode, engine: Engine, clock: FakeClock
) -> None:
    other = issue_code(engine, clock, "Other")
    with capture_logs() as logs:
        await client.post(SESSIONS, json={"code": "00000000"})
        session = await login(client, code)
        auth = bearer(session["session_token"])
        departure = await _take_first_departure(client, auth)
        await client.put(POSITION, json=GOOD_POSITION, headers=auth)
        await client.delete(CURRENT, headers=auth)
        await login(client, other)
    names = [entry["event"] for entry in logs]
    assert names == [
        "driver.login_failed",
        "driver.session_started",
        "driver.service_selected",
        "driver.session_closed",
        "driver.session_started",
    ]
    assert logs[2]["trip_id"] == departure["trip_id"]
    assert logs[2]["line"] == "93"
    assert logs[2]["direction_id"] == 0
    assert logs[2]["session_id"] == session["session_id"]
    assert logs[3]["reason"] == "ENDED"
    assert isinstance(logs[3]["duration_s"], int)
    written = repr(logs)
    for secret in (
        "00000000",
        code.plain,
        other.plain,
        session["session_token"],
        "39.47",
        "203.0.113.7",
    ):
        assert secret not in written


@pytest.mark.spec("driver_session.AC-15")
@pytest.mark.parametrize(
    "path",
    [
        f"{SESSIONS}",
        f"{DEPARTURES}?line=93&direction_id=0",
        DRIVER_API,
    ],
)
async def test_the_access_log_hides_the_address_on_driver_requests(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        logging.getLogger(ACCESS_LOGGER).info(
            _ACCESS_FORMAT, "203.0.113.7:50000", "POST", path, "1.1", 201
        )
    assert caplog.messages == [f'- - "POST {path} HTTP/1.1" 201']


@pytest.mark.spec("driver_session.AC-15")
@pytest.mark.parametrize("path", ["/api/v1/stops/508", "/api/v1/drivers", "/api/v1/driverless"])
async def test_the_access_log_of_other_paths_is_unchanged(
    client: httpx.AsyncClient, caplog: pytest.LogCaptureFixture, path: str
) -> None:
    with caplog.at_level(logging.INFO, logger=ACCESS_LOGGER):
        logging.getLogger(ACCESS_LOGGER).info(
            _ACCESS_FORMAT, "203.0.113.7:50000", "GET", path, "1.1", 200
        )
    assert caplog.messages == [f'203.0.113.7:50000 - "GET {path} HTTP/1.1" 200']


@pytest.mark.spec("driver_session.AC-15")
def test_the_address_filter_is_installed_once(engine: Engine, clock: FakeClock) -> None:
    logger = logging.getLogger(ACCESS_LOGGER)
    for _ in range(2):
        create_app(stops_settings(), drivers=driver_use_cases(engine, clock))
    assert sum(isinstance(f, DriverAddressFilter) for f in logger.filters) == 1
