"""`avisabus simulate` against the app in process (driver_gps_simulator T-02).

The simulator talks to the real driver API through `httpx.ASGITransport` (no sockets), over
`gtfs_mini` and a FakeClock that the fake `sleep` moves forward; the codes are created with the
real use case. Every request and response is recorded to check what the simulator sent.
"""

import asyncio
import json
import logging
import signal
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
import structlog
from fastapi import FastAPI
from sqlalchemy import Engine, text
from typer.testing import CliRunner, Result

import avisabus
from avisabus.adapters.inbound.cli import simulate as simulate_cli
from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.inbound.cli.main import app
from avisabus.adapters.inbound.http.app import create_app
from avisabus.adapters.inbound.http.container import DriverUseCases
from avisabus.config import ConfigurationError, Settings
from avisabus.domain.models.driver import SessionCloseReason
from avisabus.domain.ports.clock import Clock
from avisabus.logging import configure_logging
from tests.support.driver_app import (
    DRIVER_API,
    IssuedCode,
    bearer,
    driver_use_cases,
    issue_code,
    revoke_code,
)
from tests.support.drivers import RecordingListener
from tests.support.fake_clock import FakeClock
from tests.support.gtfs import GTFS_MINI
from tests.support.stops import import_feed, new_engine, stops_settings

runner = CliRunner()
NOW = datetime(2026, 11, 9, 8, 0, tzinfo=UTC)  # Monday, 09:00 in Madrid
LINE, DIRECTION = "93", 0
# Departures of line 93, direction 0, from 08:30 to 10:00 in Madrid (gtfs_mini).
FIRST_TRIP = "93_994_561_488_2271_2_023"  # 08:32
SECOND_TRIP = "93_994_561_488_2271_2_024"  # 08:40
TRIP_0848 = "93_994_561_488_2271_2_025"  # 08:48
SESSIONS = f"{DRIVER_API}/sessions"
CURRENT = f"{SESSIONS}/current"
POSITION = f"{CURRENT}/position"
SERVICE = f"{CURRENT}/service"
FAST = ("--speed-kmh", "60", "--dwell-s", "5")


@dataclass
class Exchange:
    method: str
    path: str
    headers: httpx.Headers
    body: Any
    status: int
    response: Any


class RecordingTransport(httpx.AsyncBaseTransport):
    """Forwards to the app in process and records every request with its response. `before` runs
    before forwarding a request, e.g. to change the server state at a given moment."""

    def __init__(self, inner: httpx.AsyncBaseTransport) -> None:
        self.inner = inner
        self.exchanges: list[Exchange] = []
        self.before: Callable[[httpx.Request], Awaitable[None]] | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if self.before is not None:
            await self.before(request)
        response = await self.inner.handle_async_request(request)
        content = await response.aread()
        self.exchanges.append(
            Exchange(
                method=request.method,
                path=request.url.path,
                headers=request.headers,
                body=json.loads(request.content) if request.content else None,
                status=response.status_code,
                response=json.loads(content) if content else None,
            )
        )
        return response

    def of(self, method: str, path: str) -> list[Exchange]:
        return [e for e in self.exchanges if (e.method, e.path) == (method, path)]

    def token(self) -> str:
        started = self.of("POST", SESSIONS)
        assert started and started[0].status == 201
        token: str = started[0].response["session_token"]
        return token


@dataclass
class Simulator:
    clock: FakeClock
    transport: RecordingTransport
    listener: RecordingListener
    engine: Engine
    use_cases: DriverUseCases
    server: FastAPI
    code: IssuedCode
    sleeps: list[float] = field(default_factory=list)
    on_sleep: Callable[[int], Awaitable[None]] | None = None
    """Called with the number of the wait (1, 2…) before the clock moves; it may interrupt."""

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        if self.on_sleep is not None:
            await self.on_sleep(len(self.sleeps))
        self.clock.advance(timedelta(seconds=seconds))

    def run(self, *args: str, code: str | None = None, env: dict[str, str] | None = None) -> Result:
        code_args = () if code is None and env else ("--code", code or self.code.plain)
        return runner.invoke(
            app,
            ["simulate", "--line", LINE, "--direction", str(DIRECTION), *code_args, *args],
            env=env,
        )

    def open_sessions(self) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(text("SELECT count(*) FROM driver_session")).scalar_one())

    def closed(self) -> list[SessionCloseReason]:
        return [call[2] for call in self.listener.calls if call[0] == "session_closed"]

    def _other_client(self) -> httpx.AsyncClient:
        """A client of the same app for another tablet, outside the recording."""
        transport = httpx.ASGITransport(app=self.server, raise_app_exceptions=False)
        return httpx.AsyncClient(transport=transport, base_url="http://testserver")

    async def offered_trips(self) -> list[str]:
        """Trips that `GET /departures` offers now (asked with a shift of another code)."""
        other = issue_code(self.engine, self.clock, label="Lister")
        async with self._other_client() as http:
            started = await http.post(SESSIONS, json={"code": other.plain})
            auth = bearer(started.json()["session_token"])
            listed = await http.get(
                f"{DRIVER_API}/departures",
                params={"line": LINE, "direction_id": DIRECTION},
                headers=auth,
            )
            await http.delete(CURRENT, headers=auth)
        return [d["trip_id"] for d in listed.json()["departures"]]

    async def take(self, trip_id: str) -> None:
        """Another shift (another code) takes the departure, through the API."""
        other = issue_code(self.engine, self.clock, label="Other")
        async with self._other_client() as http:
            started = await http.post(SESSIONS, json={"code": other.plain})
            auth = bearer(started.json()["session_token"])
            listed = await http.get(
                f"{DRIVER_API}/departures",
                params={"line": LINE, "direction_id": DIRECTION},
                headers=auth,
            )
            departure = next(d for d in listed.json()["departures"] if d["trip_id"] == trip_id)
            taken = await http.put(
                SERVICE,
                json={
                    "line": LINE,
                    "direction_id": DIRECTION,
                    "trip_id": trip_id,
                    "service_date": departure["service_date"],
                },
                headers=auth,
            )
            assert taken.status_code == 200, taken.text


@pytest.fixture(scope="module")
def mini_feed(tmp_path_factory: pytest.TempPathFactory) -> Path:
    path = tmp_path_factory.mktemp("simulate") / "avisabus.sqlite"
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
def local_db(db_path: Path) -> list[Path]:
    """Database the CLI reads the shapes from (the server's one unless a test changes it)."""
    return [db_path]


@pytest.fixture
def simulator(monkeypatch: pytest.MonkeyPatch, engine: Engine, local_db: list[Path]) -> Simulator:
    clock = FakeClock(NOW)
    listener = RecordingListener()
    use_cases = driver_use_cases(engine, clock, listener)
    asgi_app = create_app(stops_settings(), drivers=use_cases)
    transport = RecordingTransport(httpx.ASGITransport(app=asgi_app, raise_app_exceptions=False))
    sim = Simulator(
        clock, transport, listener, engine, use_cases, asgi_app, issue_code(engine, clock)
    )

    def runtime() -> simulate_cli.SimulatorRuntime:
        return simulate_cli.SimulatorRuntime(clock=clock, sleep=sim.sleep, transport=transport)

    def container(_settings: Settings, _clock: Clock) -> CliContainer:
        return build_cli_container(stops_settings(database_url=f"sqlite:///{local_db[0]}"), clock)

    monkeypatch.setattr(simulate_cli, "build_runtime", runtime)
    monkeypatch.setattr(simulate_cli, "build_cli_container", container)
    monkeypatch.setattr(simulate_cli, "configure_logging", lambda _level: None)
    return sim


@pytest.fixture
def real_logging(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """The real JSON logs, written to the captured output, at DEBUG."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    monkeypatch.setattr(simulate_cli, "configure_logging", configure_logging)
    monkeypatch.setenv("AVISABUS_LOG_LEVEL", "DEBUG")
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.NOTSET)
    structlog.reset_defaults()


def _chosen_trip(sim: Simulator) -> str:
    selected = sim.transport.of("PUT", SERVICE)
    assert len(selected) == 1
    trip: str = selected[0].body["trip_id"]
    return trip


def _progress_lines(result: Result) -> list[str]:
    return [line for line in result.stdout.splitlines() if line.startswith("[")]


# --- AC-01: start, choose the departure and send positions ------------------------------------


@pytest.mark.spec("driver_gps_simulator.AC-01")
@pytest.mark.spec("driver_gps_simulator.AC-03")
def test_drives_the_first_free_departure_to_its_last_stop_with_the_defaults(
    simulator: Simulator,
) -> None:
    result = simulator.run()

    assert result.exit_code == 0, result.output
    calls = [(e.method, e.path) for e in simulator.transport.exchanges]
    assert calls[:4] == [
        ("POST", SESSIONS),
        ("GET", f"{DRIVER_API}/lines"),
        ("GET", f"{DRIVER_API}/departures"),
        ("PUT", SERVICE),
    ]
    assert calls[-1] == ("DELETE", CURRENT)
    assert _chosen_trip(simulator) == FIRST_TRIP
    positions = simulator.transport.of("PUT", POSITION)
    assert len(positions) > 300  # 9.5 km at 20 km/h every 5 s, plus the stops
    assert all(e.status == 204 for e in positions)
    # AC-03: the last position reaches the last stop and the server sees the trip finished.
    states = simulator.transport.of("GET", CURRENT)
    assert states[-1].response["finished"] is True
    assert not any(state.response["finished"] for state in states[:-4])
    assert simulator.closed() == [SessionCloseReason.ENDED]
    assert simulator.open_sessions() == 0
    assert "Turno finalizado." in result.stdout


@pytest.mark.spec("driver_gps_simulator.AC-01")
def test_every_position_has_a_new_recorded_at_from_the_clock(simulator: Simulator) -> None:
    result = simulator.run("--interval-s", "4", *FAST)

    assert result.exit_code == 0, result.output
    stamps = [
        datetime.fromisoformat(e.body["recorded_at"])
        for e in simulator.transport.of("PUT", POSITION)
    ]
    assert stamps == [NOW + timedelta(seconds=4 * n) for n in range(len(stamps))]
    assert simulator.sleeps == [4.0] * (len(stamps) - 1)
    assert all(state.response["gps"] == "OK" for state in simulator.transport.of("GET", CURRENT))


@pytest.mark.spec("driver_gps_simulator.AC-01")
def test_takes_the_code_from_the_environment(simulator: Simulator) -> None:
    result = simulator.run(*FAST, env={"AVISABUS_SIM_CODE": simulator.code.plain})

    assert result.exit_code == 0, result.output
    assert simulator.transport.of("POST", SESSIONS)[0].body == {"code": simulator.code.plain}


@pytest.mark.spec("driver_gps_simulator.AC-01")
def test_skips_taken_departures_by_default(simulator: Simulator) -> None:
    asyncio.run(simulator.take(FIRST_TRIP))

    result = simulator.run(*FAST)

    assert result.exit_code == 0, result.output
    assert _chosen_trip(simulator) == SECOND_TRIP


@pytest.mark.spec("driver_gps_simulator.AC-01")
def test_chooses_the_departure_of_the_given_time(simulator: Simulator) -> None:
    result = simulator.run("--departure", "08:48", *FAST)

    assert result.exit_code == 0, result.output
    assert _chosen_trip(simulator) == TRIP_0848
    assert "salida de las 08:48" in result.stdout


@pytest.mark.spec("driver_gps_simulator.AC-01")
def test_chooses_the_given_trip(simulator: Simulator) -> None:
    result = simulator.run("--trip", SECOND_TRIP, *FAST)

    assert result.exit_code == 0, result.output
    assert _chosen_trip(simulator) == SECOND_TRIP


@pytest.mark.spec("driver_gps_simulator.AC-01")
def test_identifies_itself_with_its_user_agent(simulator: Simulator) -> None:
    result = simulator.run(*FAST)

    assert result.exit_code == 0, result.output
    assert {e.headers["user-agent"] for e in simulator.transport.exchanges} == {
        f"AvisaBus-simulator/{avisabus.__version__}"
    }


@pytest.mark.spec("driver_gps_simulator.AC-01")
@pytest.mark.parametrize(
    "args",
    [
        ("--departure", "08:48", "--trip", SECOND_TRIP),
        (
            "--departure",
            "8.48",
        ),
        (
            "--departure",
            "24:10",
        ),
        ("--speed-kmh", "0"),
        ("--interval-s", "-5"),
        ("--dwell-s", "-1"),
        ("--noise-m", "nan"),
    ],
)
def test_rejects_invalid_options_without_starting_a_shift(
    simulator: Simulator, args: tuple[str, ...]
) -> None:
    result = simulator.run(*args)

    assert result.exit_code == 2
    assert simulator.transport.exchanges == []


# --- AC-02 in the command: noise reaches the API ----------------------------------------------


@pytest.mark.spec("driver_gps_simulator.AC-02")
def test_sends_the_noisy_positions_of_the_seed(simulator: Simulator) -> None:
    def sent() -> list[tuple[float, float]]:
        return [(e.body["lat"], e.body["lon"]) for e in simulator.transport.of("PUT", POSITION)]

    assert simulator.run(*FAST).exit_code == 0
    clean = sent()
    simulator.transport.exchanges.clear()
    assert simulator.run(*FAST, "--noise-m", "10", "--seed", "3").exit_code == 0
    noisy = sent()
    simulator.transport.exchanges.clear()
    assert simulator.run(*FAST, "--noise-m", "10", "--seed", "3").exit_code == 0

    assert sent() == noisy != clean
    assert len(noisy) == len(clean)


# --- AC-03: interruption ------------------------------------------------------------------------


@pytest.mark.spec("driver_gps_simulator.AC-03")
def test_ctrl_c_ends_the_shift_and_exits_with_0(simulator: Simulator) -> None:
    async def interrupt(n: int) -> None:
        if n == 3:
            raise KeyboardInterrupt

    simulator.on_sleep = interrupt

    result = simulator.run()

    assert result.exit_code == 0, result.output
    assert len(simulator.transport.of("PUT", POSITION)) == 3
    assert simulator.transport.exchanges[-1].method == "DELETE"
    assert simulator.transport.exchanges[-1].status == 204
    assert simulator.closed() == [SessionCloseReason.ENDED]
    assert simulator.open_sessions() == 0
    assert "Interrumpido" in result.stdout


@pytest.mark.spec("driver_gps_simulator.AC-03")
def test_ctrl_c_as_asyncio_run_delivers_it_ends_the_shift(simulator: Simulator) -> None:
    """`asyncio.run` turns the first Ctrl+C into the cancellation of the main task."""

    async def cancel(n: int) -> None:
        if n == 2:
            task = asyncio.current_task()
            assert task is not None
            task.cancel()
            await asyncio.sleep(0)

    simulator.on_sleep = cancel

    result = simulator.run()

    assert result.exit_code == 0, result.output
    assert simulator.transport.exchanges[-1].method == "DELETE"
    assert simulator.closed() == [SessionCloseReason.ENDED]
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-03")
@pytest.mark.skipif(
    signal.getsignal(signal.SIGINT) is not signal.default_int_handler,
    reason="needs the default SIGINT handler, which asyncio.run replaces",
)
def test_a_real_sigint_ends_the_shift(simulator: Simulator) -> None:
    async def press_ctrl_c(n: int) -> None:
        if n == 2:
            signal.raise_signal(signal.SIGINT)
            await asyncio.sleep(0)

    simulator.on_sleep = press_ctrl_c

    result = simulator.run()

    assert result.exit_code == 0, result.output
    assert simulator.transport.exchanges[-1].method == "DELETE"
    assert simulator.open_sessions() == 0


# --- AC-04: errors exit with 1, a clear message and no open shift -----------------------------


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_an_unknown_code_exits_with_1(simulator: Simulator) -> None:
    result = simulator.run(code="00000000")

    assert result.exit_code == 1
    assert "código de conductor no es válido" in result.stderr
    assert [(e.method, e.path) for e in simulator.transport.exchanges] == [("POST", SESSIONS)]
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_a_revoked_code_exits_with_1(simulator: Simulator) -> None:
    revoke_code(simulator.engine, simulator.clock, simulator.code.code_id)

    result = simulator.run()

    assert result.exit_code == 1
    assert "código de conductor no es válido" in result.stderr
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_too_many_failed_codes_exit_with_1(simulator: Simulator) -> None:
    for _ in range(5):
        assert simulator.run(code="00000000").exit_code == 1

    result = simulator.run()

    assert result.exit_code == 1
    assert "demasiados intentos" in result.stderr
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_an_unknown_line_exits_with_1_and_ends_the_shift(simulator: Simulator) -> None:
    result = runner.invoke(
        app, ["simulate", "--line", "999", "--direction", "0", "--code", simulator.code.plain]
    )

    assert result.exit_code == 1
    assert "la línea 999 no existe" in result.stderr
    assert simulator.transport.exchanges[-1].method == "DELETE"
    assert simulator.closed() == [SessionCloseReason.ENDED]
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_an_unknown_direction_exits_with_1_and_ends_the_shift(simulator: Simulator) -> None:
    result = runner.invoke(
        app, ["simulate", "--line", LINE, "--direction", "7", "--code", simulator.code.plain]
    )

    assert result.exit_code == 1
    assert "no tiene el sentido 7" in result.stderr
    assert "0 (Passeig Marítim - Hospital Malva-rosa)" in result.stderr
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-04")
@pytest.mark.parametrize(
    ("args", "wanted"),
    [
        (("--departure", "03:00"), "la salida de las 03:00 no está"),
        (("--trip", "no-such-trip"), "el viaje no-such-trip no está"),
    ],
)
def test_a_departure_that_does_not_exist_lists_the_available_ones(
    simulator: Simulator, args: tuple[str, ...], wanted: str
) -> None:
    result = simulator.run(*args)

    assert result.exit_code == 1
    assert wanted in result.stderr
    assert "Salidas disponibles:" in result.stderr
    assert f"08:32  {FIRST_TRIP}  Avinguda del Cid" in result.stderr
    assert f"08:40  {SECOND_TRIP}" in result.stderr
    assert simulator.transport.of("PUT", SERVICE) == []
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_a_taken_departure_exits_with_1_and_leaves_the_other_shift(simulator: Simulator) -> None:
    asyncio.run(simulator.take(FIRST_TRIP))

    result = simulator.run("--trip", FIRST_TRIP)

    assert result.exit_code == 1
    assert "está ocupada" in result.stderr
    assert simulator.transport.of("PUT", SERVICE) == []
    assert simulator.closed() == [SessionCloseReason.ENDED]
    assert simulator.open_sessions() == 1  # only the other shift


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_a_departure_taken_while_choosing_it_exits_with_1(simulator: Simulator) -> None:
    async def take_first(request: httpx.Request) -> None:
        if request.method == "PUT" and request.url.path == SERVICE:
            simulator.transport.before = None
            await simulator.take(FIRST_TRIP)

    simulator.transport.before = take_first

    result = simulator.run()

    assert result.exit_code == 1
    assert simulator.transport.of("PUT", SERVICE)[0].status == 409
    assert "está ocupada" in result.stderr
    assert simulator.open_sessions() == 1


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_a_departure_with_all_departures_taken_lists_them(simulator: Simulator) -> None:
    async def take_all() -> None:
        for trip_id in await simulator.offered_trips():
            await simulator.take(trip_id)

    asyncio.run(take_all())

    result = simulator.run()

    assert result.exit_code == 1
    assert "no hay ninguna salida libre" in result.stderr
    assert "(ocupada)" in result.stderr
    assert simulator.transport.of("PUT", SERVICE) == []


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_a_trip_missing_from_the_local_database_exits_with_1(
    simulator: Simulator, local_db: list[Path], tmp_path: Path
) -> None:
    empty = tmp_path / "empty.sqlite"
    new_engine(empty).dispose()
    local_db[0] = empty

    result = simulator.run()

    assert result.exit_code == 1
    assert f"el viaje {FIRST_TRIP} no tiene trazado" in result.stderr
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_a_shift_closed_by_the_server_exits_with_1(simulator: Simulator) -> None:
    async def close_on_server(n: int) -> None:
        if n == 2:
            closed = await simulator.transport.inner.handle_async_request(
                httpx.Request(
                    "DELETE",
                    f"http://testserver{CURRENT}",
                    headers=bearer(simulator.transport.token()),
                )
            )
            assert closed.status_code == 204

    simulator.on_sleep = close_on_server

    result = simulator.run()

    assert result.exit_code == 1
    assert "el servidor ha cerrado el turno" in result.stderr
    assert simulator.open_sessions() == 0


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_an_unreachable_server_exits_with_1(
    simulator: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    def runtime() -> simulate_cli.SimulatorRuntime:
        return simulate_cli.SimulatorRuntime(
            clock=simulator.clock, sleep=simulator.sleep, transport=httpx.MockTransport(refuse)
        )

    monkeypatch.setattr(simulate_cli, "build_runtime", runtime)

    result = simulator.run("--base-url", "http://bus.invalid:8000")

    assert result.exit_code == 1
    assert "no se puede comunicar con http://bus.invalid:8000 (ConnectError)" in result.stderr


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_a_shift_that_cannot_be_ended_exits_with_1(simulator: Simulator) -> None:
    async def server_down(n: int) -> None:
        if n == 1:

            async def refuse(request: httpx.Request) -> None:
                raise httpx.ConnectError("refused", request=request)

            simulator.transport.before = refuse
            raise KeyboardInterrupt

    simulator.on_sleep = server_down

    result = simulator.run()

    assert result.exit_code == 1
    assert "no se ha podido finalizar el turno" in result.stderr


@pytest.mark.spec("driver_gps_simulator.AC-04")
def test_an_unexpected_failure_ends_the_shift_without_a_traceback(
    simulator: Simulator,
) -> None:
    async def explode(n: int) -> None:
        if n == 1:
            raise RuntimeError(simulator.code.plain)

    simulator.on_sleep = explode

    result = simulator.run()

    assert result.exit_code == 1
    assert "fallo inesperado (RuntimeError)" in result.stderr
    assert simulator.code.plain not in result.output
    assert "Traceback" not in result.output
    assert simulator.open_sessions() == 0


# --- AC-05: console output -----------------------------------------------------------------------


@pytest.mark.spec("driver_gps_simulator.AC-05")
def test_prints_distance_next_stop_and_shift_state_on_every_send(simulator: Simulator) -> None:
    result = simulator.run("--interval-s", "5", "--dwell-s", "10")

    assert result.exit_code == 0, result.output
    lines = _progress_lines(result)
    states = simulator.transport.of("GET", CURRENT)
    assert len(lines) == len(simulator.transport.of("PUT", POSITION)) == len(states)
    assert lines[0] == (
        "[     0 s] recorrido      0 m · en parada Avinguda del Cid · próxima parada: "
        f"{_next(states[0])} · turno: GPS OK"
    )
    for line, state in zip(lines, states, strict=True):
        gps = state.response["gps"]
        assert f"próxima parada: {_next(state)} · turno: GPS {gps}" in line
    travelled = [float(line.split("recorrido")[1].split("m ·")[0]) for line in lines]
    assert travelled == sorted(travelled)
    assert 9_000 < travelled[-1] < 10_000
    assert lines[-1].endswith("próxima parada: ninguna · turno: GPS OK · recorrido terminado")
    assert lines[1].startswith("[     5 s] recorrido      0 m · en parada")
    assert any(" · en marcha · " in line for line in lines)


def _next(state: Exchange) -> str:
    upcoming = state.response["upcoming"]
    if not upcoming:
        return "ninguna"
    stop = upcoming[0]
    return f"{stop['name']} ({stop['stop_id']}) a {stop['distance_m']:.0f} m"


@pytest.mark.spec("driver_gps_simulator.AC-05")
def test_never_shows_the_code_or_the_token(simulator: Simulator, real_logging: None) -> None:
    result = simulator.run(*FAST, env={"AVISABUS_SIM_CODE": simulator.code.plain})

    assert result.exit_code == 0, result.output
    token = simulator.transport.token()
    output = result.output
    assert '"event"' in output  # the JSON logs are in the captured output too
    assert simulator.code.plain not in output
    assert f"{simulator.code.plain[:4]} {simulator.code.plain[4:]}" not in output
    assert token not in output


@pytest.mark.spec("driver_gps_simulator.AC-05")
def test_never_shows_the_code_when_it_fails(simulator: Simulator, real_logging: None) -> None:
    result = simulator.run("--trip", "no-such-trip")

    assert result.exit_code == 1
    assert simulator.code.plain not in result.output
    assert simulator.transport.token() not in result.output


@pytest.mark.spec("driver_gps_simulator.AC-05")
def test_the_help_does_not_show_the_code_of_the_environment(simulator: Simulator) -> None:
    result = runner.invoke(
        app, ["simulate", "--help"], env={"AVISABUS_SIM_CODE": simulator.code.plain}
    )

    assert result.exit_code == 0
    assert "AVISABUS_SIM_CODE" in result.stdout
    assert simulator.code.plain not in result.output


@pytest.mark.spec("driver_gps_simulator.AC-05")
def test_a_broken_configuration_exits_with_1_without_a_traceback(
    simulator: Simulator, monkeypatch: pytest.MonkeyPatch
) -> None:
    def broken(_settings: Settings, _clock: Clock) -> CliContainer:
        raise ConfigurationError("AVISABUS_STOP_TOKEN_SECRET is required")

    monkeypatch.setattr(simulate_cli, "build_cli_container", broken)

    result = simulator.run()

    assert result.exit_code == 1
    assert "no se puede preparar la simulación (AVISABUS_STOP_TOKEN_SECRET" in result.stderr
    assert "Traceback" not in result.output
    assert simulator.code.plain not in result.output
    assert simulator.transport.exchanges == []
