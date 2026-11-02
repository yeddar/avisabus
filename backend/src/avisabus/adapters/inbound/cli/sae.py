"""`avisabus sae …`: query and record the SAE (sae_arrivals_source design §3 "CLI").

    avisabus sae fetch --stop ID
    avisabus sae record --stop ID [--stop ID ...] --interval S --duration S --out DIR

Both use the HTTP source directly (no cache, no replay): they exist to look at the real SAE.
`record` writes every raw response (also failures) and always exits 0 once started (AC-17).

Exit codes: 0 success; 1 `fetch` could not get the arrivals; 2 invalid options or `--out`
already holds a session.
"""

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

import httpx
import typer

from avisabus.adapters.outbound.clock import SystemClock
from avisabus.adapters.outbound.sae.http_source import (
    RawObserver,
    SaeHttpArrivalsSource,
    build_user_agent,
)
from avisabus.adapters.outbound.sae.recording import (
    SESSION_FILE,
    RecordingArrivalsSource,
    SaeSession,
)
from avisabus.config import Settings
from avisabus.domain.errors import ArrivalsUnavailableError
from avisabus.domain.models.arrivals import ArrivalKind, ArrivalsSnapshot, SaeArrival
from avisabus.domain.ports.clock import Clock
from avisabus.logging import configure_logging

EXIT_UNAVAILABLE = 1
EXIT_USAGE = 2
SOURCE_FORMAT = "qrphp_html"
MADRID = ZoneInfo("Europe/Madrid")

sae_app = typer.Typer(no_args_is_help=True, help="SAE real-time arrivals: query and record.")


@dataclass(frozen=True, slots=True)
class SaeCliRuntime:
    """What the commands depend on; tests replace `build_runtime`."""

    settings: Settings
    clock: Clock
    transport: httpx.AsyncBaseTransport | None
    """`None` → the real network."""
    sleep: Callable[[float], Awaitable[None]]


def build_runtime() -> SaeCliRuntime:
    settings = Settings()
    configure_logging(settings.log_level)
    return SaeCliRuntime(
        settings=settings, clock=SystemClock(), transport=None, sleep=asyncio.sleep
    )


@sae_app.command("fetch")
def fetch(
    stop: Annotated[str, typer.Option("--stop", help="Stop id (GTFS stop_id = SAE code).")],
) -> None:
    """Show the normalised arrivals of a stop, or why they are not available."""
    runtime = build_runtime()
    try:
        snapshot = asyncio.run(_fetch(runtime, stop))
    except ArrivalsUnavailableError as error:
        typer.echo(
            f"ERROR: llegadas no disponibles para la parada {stop} (motivo: {error.reason})",
            err=True,
        )
        raise typer.Exit(EXIT_UNAVAILABLE) from None
    typer.echo(
        f"Parada {snapshot.stop_id} · {_utc(snapshot.fetched_at)} · "
        f"{len(snapshot.arrivals)} llegadas"
    )
    if not snapshot.arrivals:
        typer.echo("  Sin llegadas.")
    for arrival in snapshot.arrivals:
        typer.echo(f"  {arrival.line:<4} {arrival.destination:<28} {_when(arrival)}")


@sae_app.command("record")
def record(
    stops: Annotated[
        list[str],
        typer.Option("--stop", help="Stop id to record (repeatable).", show_default=False),
    ],
    interval: Annotated[int, typer.Option("--interval", min=1, help="Seconds between queries.")],
    duration: Annotated[int, typer.Option("--duration", min=1, help="Seconds to record.")],
    out: Annotated[Path, typer.Option("--out", help="Session directory to create.")],
) -> None:
    """Query every stop each `interval` seconds for `duration` seconds, recording responses."""
    if (out / SESSION_FILE).exists():
        typer.echo(f"ERROR: {out} ya contiene una sesión grabada; elige otro --out", err=True)
        raise typer.Exit(EXIT_USAGE)
    runtime = build_runtime()
    unique_stops = tuple(dict.fromkeys(stops))
    failures = asyncio.run(_record(runtime, unique_stops, interval, duration, out))
    typer.echo(f"Sesión grabada en {out} ({failures} consultas fallidas).")


async def _fetch(runtime: SaeCliRuntime, stop: str) -> ArrivalsSnapshot:
    async with httpx.AsyncClient(transport=runtime.transport) as client:
        return await _http_source(runtime, client).get_arrivals(stop)


async def _record(
    runtime: SaeCliRuntime, stops: tuple[str, ...], interval: int, duration: int, out: Path
) -> int:
    clock = runtime.clock
    started = clock.now()
    session = SaeSession(
        started_at=started,
        stops=stops,
        interval_s=interval,
        source_url_template=runtime.settings.sae_url_template,
        source_format=SOURCE_FORMAT,
    )
    recorder = RecordingArrivalsSource(out, session)
    cycles = math.ceil(duration / interval)
    failures = 0
    async with httpx.AsyncClient(transport=runtime.transport) as client:
        source = _http_source(runtime, client, on_raw=recorder)
        for cycle in range(cycles):
            for stop in stops:
                offset = int((clock.now() - started).total_seconds())
                try:
                    snapshot = await source.get_arrivals(stop)
                except ArrivalsUnavailableError as error:
                    failures += 1
                    typer.echo(f"[+{offset:>4}s] {stop}: error ({error.reason})")
                else:
                    typer.echo(f"[+{offset:>4}s] {stop}: {len(snapshot.arrivals)} llegadas")
            if cycle + 1 < cycles:
                next_cycle = started + timedelta(seconds=(cycle + 1) * interval)
                await runtime.sleep(max(0.0, (next_cycle - clock.now()).total_seconds()))
    return failures


def _http_source(
    runtime: SaeCliRuntime, client: httpx.AsyncClient, on_raw: RawObserver | None = None
) -> SaeHttpArrivalsSource:
    settings = runtime.settings
    return SaeHttpArrivalsSource(
        client=client,
        url_template=settings.sae_url_template,
        clock=runtime.clock,
        timeout_s=settings.sae_timeout_s,
        user_agent=build_user_agent(settings.sae_contact),
        on_raw=on_raw,
    )


def _when(arrival: SaeArrival) -> str:
    if arrival.kind is ArrivalKind.CLOCK_TIME:
        return arrival.arrival_at.astimezone(MADRID).strftime("%H:%M")
    return f"{arrival.minutes} min"


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
