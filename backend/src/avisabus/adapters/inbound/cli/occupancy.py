"""`avisabus occupancy override …`: per-line occupancy overrides for demos (occupancy_sensor §3).

    avisabus occupancy override --line L --level FREE|MEDIUM|FULL [--minutes 30]
    avisabus occupancy override --line L --clear
    avisabus occupancy override --list

Exit codes: 0 success, 2 unknown line or invalid options.
"""

import asyncio
from datetime import UTC, datetime
from typing import Annotated, NoReturn

import typer

from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.outbound.clock import SystemClock
from avisabus.application.set_occupancy_override import (
    DEFAULT_OVERRIDE_MINUTES,
    ClearOccupancyOverrideCommand,
    ListOccupancyOverridesQuery,
    SetOccupancyOverrideCommand,
)
from avisabus.config import Settings
from avisabus.domain.errors import UnknownLineError
from avisabus.domain.models.occupancy import OccupancyLevel
from avisabus.logging import configure_logging

EXIT_UNKNOWN_LINE = 2

occupancy_app = typer.Typer(no_args_is_help=True, help="Occupancy: demo overrides.")


def _container() -> CliContainer:
    settings = Settings()
    configure_logging(settings.log_level)
    return build_cli_container(settings, SystemClock())


@occupancy_app.command("override")
def override(
    line: Annotated[str | None, typer.Option("--line", help="Commercial line, e.g. 93.")] = None,
    level: Annotated[
        OccupancyLevel | None,
        typer.Option("--level", case_sensitive=False, help="Forced occupancy level."),
    ] = None,
    minutes: Annotated[
        int | None,
        typer.Option(
            "--minutes", min=1, help=f"Duration (default {DEFAULT_OVERRIDE_MINUTES} minutes)."
        ),
    ] = None,
    clear: Annotated[bool, typer.Option("--clear", help="Remove the line's override.")] = False,
    list_: Annotated[bool, typer.Option("--list", help="Show the active overrides.")] = False,
) -> None:
    """Force the occupancy level of every trip of a line, clear it or list the active ones."""
    if list_:
        if line is not None or level is not None or minutes is not None or clear:
            raise typer.BadParameter("--list does not take other options")
        _list()
        return
    if line is None:
        raise typer.BadParameter("--line is required (or use --list)")
    if clear:
        if level is not None or minutes is not None:
            raise typer.BadParameter("--clear does not take --level or --minutes")
        _clear(line)
        return
    if level is None:
        raise typer.BadParameter("--level is required (or use --clear)")
    _set(line, level, DEFAULT_OVERRIDE_MINUTES if minutes is None else minutes)


def _set(line: str, level: OccupancyLevel, minutes: int) -> None:
    container = _container()
    try:
        result = asyncio.run(
            container.set_occupancy_override.execute(
                SetOccupancyOverrideCommand(line=line, level=level, minutes=minutes)
            )
        )
    except UnknownLineError as error:
        _unknown_line(error)
    finally:
        container.close()
    typer.echo(
        f"Forzado de ocupación: línea {result.line} → {result.level.value} "
        f"hasta {_utc(result.expires_at)}"
    )


def _clear(line: str) -> None:
    container = _container()
    try:
        removed = asyncio.run(
            container.clear_occupancy_override.execute(ClearOccupancyOverrideCommand(line))
        )
    except UnknownLineError as error:
        _unknown_line(error)
    finally:
        container.close()
    if removed:
        typer.echo(f"Forzado eliminado para la línea {line}.")
    else:
        typer.echo(f"La línea {line} no tenía ningún forzado activo.")


def _list() -> None:
    container = _container()
    try:
        active = asyncio.run(
            container.list_occupancy_overrides.execute(ListOccupancyOverridesQuery())
        )
    finally:
        container.close()
    if not active:
        typer.echo("No hay forzados de ocupación activos.")
        return
    typer.echo("Forzados de ocupación activos:")
    for item in active:
        typer.echo(f"  Línea {item.line} · {item.level.value} · caduca {_utc(item.expires_at)}")


def _unknown_line(error: UnknownLineError) -> NoReturn:
    typer.echo(f"ERROR: la línea {error.line} no existe en la red activa", err=True)
    raise typer.Exit(EXIT_UNKNOWN_LINE)


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
