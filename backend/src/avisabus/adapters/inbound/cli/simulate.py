"""`avisabus simulate`: a driver's tablet along a trip, through the driver API (CU-14).

    avisabus simulate --line L --direction D [--departure HH:MM | --trip TRIP_ID]
        [--speed-kmh 20] [--interval-s 5] [--dwell-s 15] [--noise-m 0 --seed S]
        [--base-url http://localhost:8000]          (code in --code or AVISABUS_SIM_CODE)

It starts a shift, chooses a departure and sends positions along the shape of the trip, stopping
at its stops, as the tablet does (driver_gps_simulator design §1). The shape and the stops of the
trip come from the local database (the simulator runs next to the server, on the same network);
everything else goes through the HTTP API. Whatever happens once the shift is open, including
Ctrl+C, the shift is ended with `DELETE …/current` (AC-03, AC-04).

Privacy (AC-05): neither the code nor the session token are ever printed or logged.

Exit codes: 0 last stop reached or interrupted by the user, 1 the simulation could not run (AC-04)
or the shift could not be ended, 2 invalid options.
"""

import asyncio
import logging
import math
import re
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, time
from typing import Annotated, Any

import httpx
import typer

import avisabus
from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.outbound.clock import SystemClock
from avisabus.adapters.outbound.persistence.sqlite_network import SqliteNetworkRepository
from avisabus.application.driver_sessions import TripRoute, TripRoutes
from avisabus.config import ConfigurationError, Settings
from avisabus.domain.ports.clock import Clock
from avisabus.domain.services.occupancy_simulation import LOCAL_TIMEZONE
from avisabus.domain.services.route_simulation import SimulatedFix, simulate_route
from avisabus.logging import configure_logging

EXIT_OK = 0
EXIT_FAILURE = 1
DRIVER_API = "/api/v1/driver"
USER_AGENT = f"AvisaBus-simulator/{avisabus.__version__}"
CODE_ENVVAR = "AVISABUS_SIM_CODE"
HTTP_TIMEOUT_S = 10.0
ACCURACY_M = 5.0
"""`accuracy_m` of every position: the simulated GPS is at least this good (local decision)."""
_DEPARTURE_FORMAT = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
_QUIET_LOGGERS = ("httpx", "httpcore")

sim_app = typer.Typer(help="Simulate a driver's tablet along a trip, through the driver API.")


@dataclass(frozen=True, slots=True)
class SimulatorRuntime:
    """What the tests replace (design §3): the clock of `recorded_at`, the wait between two
    positions and the HTTP transport (`None`: the real network)."""

    clock: Clock
    sleep: Callable[[float], Awaitable[None]]
    transport: httpx.AsyncBaseTransport | None = None


def build_runtime() -> SimulatorRuntime:
    return SimulatorRuntime(clock=SystemClock(), sleep=asyncio.sleep)


@dataclass(frozen=True, slots=True)
class SimulationOptions:
    line: str
    direction: int
    departure: time | None
    trip: str | None
    speed_mps: float
    interval_s: float
    dwell_s: float
    noise_m: float
    seed: int | None
    base_url: str
    code: str = field(repr=False)


class SimulationAbortedError(Exception):
    """The simulation cannot go on: `lines` explain why (to stderr) and it exits with 1."""

    def __init__(self, *lines: str) -> None:
        super().__init__()
        self.lines = lines


@sim_app.callback(invoke_without_command=True)
def simulate(
    line: Annotated[str, typer.Option("--line", help="Commercial line, e.g. 93.")],
    direction: Annotated[int, typer.Option("--direction", help="direction_id, e.g. 0.")],
    code: Annotated[
        str,
        typer.Option(
            "--code",
            envvar=CODE_ENVVAR,
            show_envvar=True,
            show_default=False,
            help="Driver access code (better in the environment variable).",
        ),
    ],
    departure: Annotated[
        str | None,
        typer.Option(
            "--departure",
            metavar="HH:MM",
            help="Departure time from the first stop (default: the first free departure).",
        ),
    ] = None,
    trip: Annotated[
        str | None, typer.Option("--trip", metavar="TRIP_ID", help="trip_id of the departure.")
    ] = None,
    speed_kmh: Annotated[float, typer.Option("--speed-kmh", help="Speed in km/h.")] = 20.0,
    interval_s: Annotated[
        float, typer.Option("--interval-s", help="Seconds between two positions.")
    ] = 5.0,
    dwell_s: Annotated[float, typer.Option("--dwell-s", help="Seconds stopped at each stop.")] = (
        15.0
    ),
    noise_m: Annotated[
        float, typer.Option("--noise-m", help="Maximum GPS noise in metres (0: none).")
    ] = 0.0,
    seed: Annotated[int | None, typer.Option("--seed", help="Seed of the noise.")] = None,
    base_url: Annotated[
        str, typer.Option("--base-url", help="Base URL of the AvisaBus server.")
    ] = "http://localhost:8000",
) -> None:
    """Start a shift, drive a departure of the line to its last stop and end the shift."""
    options = SimulationOptions(
        line=line,
        direction=direction,
        departure=_departure_time(departure, trip),
        trip=trip,
        speed_mps=_positive(speed_kmh, "--speed-kmh") / 3.6,
        interval_s=_positive(interval_s, "--interval-s"),
        dwell_s=_not_negative(dwell_s, "--dwell-s"),
        noise_m=_not_negative(noise_m, "--noise-m"),
        seed=seed,
        base_url=base_url,
        code=code,
    )
    runtime = build_runtime()
    try:
        container = _container(runtime.clock)
    except Exception as error:  # no traceback: its local variables include the code
        detail = str(error) if isinstance(error, ConfigurationError) else type(error).__name__
        typer.echo(f"ERROR: no se puede preparar la simulación ({detail}).", err=True)
        raise typer.Exit(EXIT_FAILURE) from None
    try:
        routes = TripRoutes(SqliteNetworkRepository(container.engine))
        status = asyncio.run(run_simulation(options, routes, runtime))
    finally:
        container.close()
    raise typer.Exit(status)


def _container(clock: Clock) -> CliContainer:
    settings = Settings()
    configure_logging(settings.log_level)
    for name in _QUIET_LOGGERS:  # one line per request would bury the progress lines
        logging.getLogger(name).setLevel(logging.WARNING)
    return build_cli_container(settings, clock)


def _departure_time(departure: str | None, trip: str | None) -> time | None:
    if departure is None:
        return None
    if trip is not None:
        raise typer.BadParameter("use --departure or --trip, not both", param_hint="--departure")
    match = _DEPARTURE_FORMAT.match(departure)
    if match is None:
        raise typer.BadParameter("expected HH:MM, e.g. 08:32", param_hint="--departure")
    return time(int(match.group(1)), int(match.group(2)))


def _positive(value: float, name: str) -> float:
    if not (math.isfinite(value) and value > 0):
        raise typer.BadParameter("must be greater than 0", param_hint=name)
    return value


def _not_negative(value: float, name: str) -> float:
    if not (math.isfinite(value) and value >= 0):
        raise typer.BadParameter("must not be negative", param_hint=name)
    return value


async def run_simulation(
    options: SimulationOptions, routes: TripRoutes, runtime: SimulatorRuntime
) -> int:
    """The whole simulation; the exit code. The shift, if it was started, is always ended."""
    async with httpx.AsyncClient(
        base_url=options.base_url,
        transport=runtime.transport,
        headers={"User-Agent": USER_AGENT},
        timeout=HTTP_TIMEOUT_S,
    ) as client:
        api = DriverApiClient(client, options.base_url)
        status = EXIT_FAILURE
        try:
            await api.start(options.code)
            await _drive(api, options, routes, runtime)
            status = EXIT_OK
        except SimulationAbortedError as aborted:
            for message in aborted.lines:
                typer.echo(message, err=True)
        except (KeyboardInterrupt, asyncio.CancelledError):
            # Ctrl+C: `asyncio.run` cancels the task (or the interrupt reaches the coroutine).
            _consume_cancellation()
            typer.echo("Interrumpido por el usuario.")
            status = EXIT_OK
        except Exception as error:  # never a traceback with local variables
            typer.echo(f"ERROR: fallo inesperado ({type(error).__name__}).", err=True)
        finally:
            if not await api.end():
                status = EXIT_FAILURE
        return status


def _consume_cancellation() -> None:
    task = asyncio.current_task()
    if task is not None:
        task.uncancel()


async def _drive(
    api: "DriverApiClient",
    options: SimulationOptions,
    routes: TripRoutes,
    runtime: SimulatorRuntime,
) -> None:
    await _check_line(api, options)
    departures = await api.departures(options.line, options.direction)
    chosen = _choose(departures, options)
    route = routes.of(chosen["trip_id"])
    if route is None:
        raise SimulationAbortedError(
            f"ERROR: el viaje {chosen['trip_id']} no tiene trazado o paradas en la base de datos "
            "local (¿es la misma red que la del servidor?)."
        )
    await api.select(
        {
            "line": options.line,
            "direction_id": options.direction,
            "trip_id": chosen["trip_id"],
            "service_date": chosen["service_date"],
        }
    )
    typer.echo(
        f"Turno iniciado · línea {options.line} sentido {options.direction} · "
        f"salida de las {_local_hhmm(chosen['departure_at'])} desde {chosen['first_stop_name']} "
        f"hacia {chosen['headsign']} · viaje {chosen['trip_id']}"
    )
    await _send_positions(api, options, route, runtime)
    typer.echo("Última parada alcanzada: fin del recorrido.")


async def _check_line(api: "DriverApiClient", options: SimulationOptions) -> None:
    lines = await api.lines()
    found = next((item for item in lines if item["line"] == options.line), None)
    if found is None:
        raise SimulationAbortedError(f"ERROR: la línea {options.line} no existe en la red activa.")
    directions = found["directions"]
    if all(item["direction_id"] != options.direction for item in directions):
        available = ", ".join(f"{d['direction_id']} ({d['headsign']})" for d in directions)
        raise SimulationAbortedError(
            f"ERROR: la línea {options.line} no tiene el sentido {options.direction}. "
            f"Sentidos: {available or 'ninguno'}."
        )


def _choose(departures: list[dict[str, Any]], options: SimulationOptions) -> dict[str, Any]:
    """The departure to drive (AC-01): the chosen one, or the first free one."""
    of_line = f"de la línea {options.line} sentido {options.direction}"
    if options.trip is not None:
        wanted = f"el viaje {options.trip}"
        matches = [d for d in departures if d["trip_id"] == options.trip]
    elif options.departure is not None:
        wanted = f"la salida de las {options.departure.strftime('%H:%M')}"
        matches = [d for d in departures if _local_time(d["departure_at"]) == options.departure]
    else:
        free = [d for d in departures if not d["taken"]]
        if not free:
            raise SimulationAbortedError(
                f"ERROR: no hay ninguna salida libre {of_line} ahora.", *_listing(departures)
            )
        return free[0]
    if not matches:
        raise SimulationAbortedError(
            f"ERROR: {wanted} no está entre las salidas {of_line}.", *_listing(departures)
        )
    free = [d for d in matches if not d["taken"]]
    if not free:
        raise SimulationAbortedError(
            f"ERROR: {wanted} está ocupada: otro turno abierto ya la lleva."
        )
    return free[0]


def _listing(departures: Sequence[dict[str, Any]]) -> tuple[str, ...]:
    if not departures:
        return ("No hay salidas entre 30 min antes y 60 min después de ahora.",)
    return (
        "Salidas disponibles:",
        *(
            f"  {_local_hhmm(d['departure_at'])}  {d['trip_id']}  "
            f"{d['first_stop_name']} → {d['headsign']}{'  (ocupada)' if d['taken'] else ''}"
            for d in departures
        ),
    )


def _local_time(value: str) -> time:
    local = datetime.fromisoformat(value).astimezone(LOCAL_TIMEZONE)
    return time(local.hour, local.minute)


def _local_hhmm(value: str) -> str:
    return _local_time(value).strftime("%H:%M")


async def _send_positions(
    api: "DriverApiClient",
    options: SimulationOptions,
    route: TripRoute,
    runtime: SimulatorRuntime,
) -> None:
    stops = [(stop.stop_id, distance) for stop, distance in route.stops]
    names = {stop.stop_id: stop.name for stop, _ in route.stops}
    start_m = route.stops[0][1]
    fixes = simulate_route(
        route.shape,
        stops,
        options.speed_mps,
        options.interval_s,
        options.dwell_s,
        options.noise_m,
        options.seed,
    )
    for n, fix in enumerate(fixes):
        if n > 0:
            await runtime.sleep(options.interval_s)
        # A new `recorded_at` for every fix, also while stopped: a resend of the same one would
        # only be a sign of life (driver_session AC-08 v1.3).
        await api.send_position(fix, runtime.clock.now())
        state = await api.state()
        typer.echo(_progress_line(fix, fix.distance_m - start_m, state, names))


def _progress_line(
    fix: SimulatedFix, travelled_m: float, state: dict[str, Any], names: dict[str, str]
) -> str:
    """Distance travelled, next stop and state of the shift (AC-05), never the code or token."""
    where = "en marcha" if fix.at_stop is None else f"en parada {names[fix.at_stop]}"
    upcoming = state["upcoming"]
    if upcoming:
        following = upcoming[0]
        next_stop = (
            f"{following['name']} ({following['stop_id']}) a {following['distance_m']:.0f} m"
        )
    else:
        next_stop = "ninguna"
    shift = f"GPS {state['gps']}"
    if state["off_route"]:
        shift += " · fuera de ruta"
    if state["finished"]:
        shift += " · recorrido terminado"
    return (
        f"[{fix.elapsed_s:>6.0f} s] recorrido {travelled_m:>6.0f} m · {where} · "
        f"próxima parada: {next_stop} · turno: {shift}"
    )


class DriverApiClient:
    """The calls of the tablet to `/api/v1/driver` (driver_session design §3). The token is only
    kept in the `Authorization` header and never leaves this object."""

    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base_url = base_url
        self._auth: dict[str, str] | None = None

    def __repr__(self) -> str:
        return f"DriverApiClient(base_url={self._base_url!r})"

    async def start(self, code: str) -> None:
        response = await self._send("POST", "/sessions", json={"code": code})
        if response.status_code == 201:
            token = response.json()["session_token"]
            self._auth = {"Authorization": f"Bearer {token}"}
            return
        if response.status_code == 401:
            raise SimulationAbortedError(
                "ERROR: el código de conductor no es válido (no existe o está revocado)."
            )
        if response.status_code == 429:
            raise SimulationAbortedError(
                "ERROR: demasiados intentos fallidos desde esta dirección. Vuelve a intentarlo "
                f"dentro de {response.headers.get('Retry-After', '?')} s."
            )
        raise self._unexpected(response, "al iniciar el turno")

    async def lines(self) -> list[dict[str, Any]]:
        response = await self._authorized("GET", "/lines")
        self._expect(response, 200, "al pedir las líneas")
        lines: list[dict[str, Any]] = response.json()["lines"]
        return lines

    async def departures(self, line: str, direction_id: int) -> list[dict[str, Any]]:
        response = await self._authorized(
            "GET", "/departures", params={"line": line, "direction_id": direction_id}
        )
        self._expect(response, 200, "al pedir las salidas")
        departures: list[dict[str, Any]] = response.json()["departures"]
        return departures

    async def select(self, service: dict[str, Any]) -> None:
        response = await self._authorized("PUT", "/sessions/current/service", json=service)
        if response.status_code == 409:
            raise SimulationAbortedError(
                f"ERROR: la salida del viaje {service['trip_id']} está ocupada: otro turno "
                "abierto ya la lleva."
            )
        if response.status_code == 422:
            raise SimulationAbortedError(
                f"ERROR: la salida del viaje {service['trip_id']} ya no se puede elegir."
            )
        self._expect(response, 200, "al elegir la salida")

    async def send_position(self, fix: SimulatedFix, recorded_at: datetime) -> None:
        response = await self._authorized(
            "PUT",
            "/sessions/current/position",
            json={
                "lat": fix.lat,
                "lon": fix.lon,
                "accuracy_m": ACCURACY_M,
                "recorded_at": recorded_at.isoformat(),
            },
        )
        self._expect(response, 204, "al enviar la posición")

    async def state(self) -> dict[str, Any]:
        response = await self._authorized("GET", "/sessions/current")
        self._expect(response, 200, "al pedir el estado del turno")
        state: dict[str, Any] = response.json()
        return state

    async def end(self) -> bool:
        """Ends the shift, if one was started; `False` if it may still be open."""
        if self._auth is None:
            return True
        try:
            response = await self._authorized("DELETE", "/sessions/current")
        except SimulationAbortedError as aborted:
            for message in aborted.lines:
                typer.echo(message, err=True)
            response = None
        if response is not None and response.status_code in (204, 401):  # 401: already closed
            self._auth = None
            typer.echo("Turno finalizado.")
            return True
        typer.echo(
            "ERROR: no se ha podido finalizar el turno; el servidor lo cerrará por inactividad.",
            err=True,
        )
        return False

    async def _authorized(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = await self._send(method, path, headers=self._auth, **kwargs)
        if response.status_code == 401 and method != "DELETE":  # DELETE: already closed
            raise SimulationAbortedError("ERROR: el servidor ha cerrado el turno.")
        if response.status_code == 503:
            raise SimulationAbortedError("ERROR: el servidor no tiene ninguna red GTFS activa.")
        return response

    async def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            return await self._client.request(method, f"{DRIVER_API}{path}", **kwargs)
        except httpx.HTTPError as error:
            raise SimulationAbortedError(
                f"ERROR: no se puede comunicar con {self._base_url} ({type(error).__name__})."
            ) from None

    def _expect(self, response: httpx.Response, status: int, doing: str) -> None:
        if response.status_code != status:
            raise self._unexpected(response, doing)

    @staticmethod
    def _unexpected(response: httpx.Response, doing: str) -> SimulationAbortedError:
        return SimulationAbortedError(
            f"ERROR: respuesta inesperada del servidor {doing} (HTTP {response.status_code})."
        )
