"""`avisabus gtfs import PATH` and `avisabus gtfs info [--directions]` (gtfs_import design §3).

Exit codes: 0 success, 1 no feed imported (`info`), 2 validation or import error.
"""

import asyncio
from datetime import UTC, date
from pathlib import Path
from typing import Annotated, NoReturn

import structlog
import typer

from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.outbound.clock import SystemClock
from avisabus.application.errors import GtfsDataError, GtfsValidationError
from avisabus.application.get_feed_info import GetFeedInfoQuery
from avisabus.application.import_gtfs_feed import ImportGtfsFeedCommand
from avisabus.config import Settings
from avisabus.domain.models.network import FeedVersion
from avisabus.domain.ports.gtfs_import import DirectionReport
from avisabus.domain.services.feed_validity import Expired, Expiring, FeedValidityStatus
from avisabus.logging import configure_logging

EXIT_NO_FEED = 1
EXIT_IMPORT_ERROR = 2

log = structlog.get_logger(__name__)

gtfs_app = typer.Typer(no_args_is_help=True, help="GTFS feed: import and status.")


def _container() -> CliContainer:
    settings = Settings()
    configure_logging(settings.log_level)
    return build_cli_container(settings, SystemClock())


@gtfs_app.command("import")
def import_feed(
    path: Annotated[Path, typer.Argument(help="Feed directory or .zip file.")],
) -> None:
    """Import a GTFS feed and make it the active version."""
    container = _container()
    try:
        result = asyncio.run(container.import_gtfs_feed.execute(ImportGtfsFeedCommand(path)))
    except GtfsValidationError as error:
        _fail(_validation_message(error))
    except GtfsDataError as error:
        _fail(
            f"ERROR: valor inválido en {error.file}, línea {error.line_number}: {error.detail}. "
            "Importación descartada; la versión activa no cambia."
        )
    except Exception as error:
        log.error("gtfs.import_failed", error_type=type(error).__name__)
        _fail(
            f"ERROR: la importación ha fallado ({type(error).__name__}). "
            "Importación descartada; la versión activa no cambia."
        )
    finally:
        container.close()
    feed = result.feed
    suffix = f", feed_version {feed.feed_version}" if feed.feed_version else ""
    typer.echo(f"Feed importado (versión {feed.version_id}{suffix})")
    _echo_feed_summary(feed)
    _report_validity(result.validity, feed.end_date)


@gtfs_app.command("info")
def info(
    directions: Annotated[
        bool, typer.Option("--directions", help="List every line direction and its origin.")
    ] = False,
) -> None:
    """Show the active feed, its validity and counts."""
    container = _container()
    try:
        feed_info = asyncio.run(
            container.get_feed_info.execute(GetFeedInfoQuery(include_directions=directions))
        )
    finally:
        container.close()
    if feed_info is None:
        typer.echo("No hay ningún feed importado. Usa `avisabus gtfs import PATH`.")
        raise typer.Exit(EXIT_NO_FEED)
    feed = feed_info.feed
    suffix = f" (feed_version {feed.feed_version})" if feed.feed_version else ""
    typer.echo(f"Versión activa: {feed.version_id}{suffix}")
    imported = feed.imported_at.astimezone(UTC).strftime("%Y-%m-%d %H:%M")
    typer.echo(f"Importado: {imported} UTC")
    _echo_feed_summary(feed)
    _report_validity(feed_info.validity, feed.end_date)
    if directions:
        typer.echo("")
        for report in feed_info.directions:
            _echo_direction(report)


def _fail(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(EXIT_IMPORT_ERROR)


def _validation_message(error: GtfsValidationError) -> str:
    if error.column is not None:
        return f"ERROR: falta la columna {error.column} en {error.file}"
    if error.reason is not None:
        return f"ERROR: no se puede leer {error.file} ({error.reason})"
    return f"ERROR: falta {error.file}"


def _number(value: int) -> str:
    return f"{value:,}".replace(",", " ")


def _echo_feed_summary(feed: FeedVersion) -> None:
    counts = feed.counts
    typer.echo(f"Vigencia: {feed.start_date.isoformat()} → {feed.end_date.isoformat()}")
    typer.echo(
        f"Líneas: {_number(counts.get('lines', 0))} · Paradas: {_number(counts.get('stops', 0))}"
        f" · Viajes: {_number(counts.get('trips', 0))}"
        f" · Horarios de parada: {_number(counts.get('stop_times', 0))}"
    )
    typer.echo(f"route_id sin viajes ignorados: {_number(counts.get('ignored_route_ids', 0))}")


def _report_validity(status: FeedValidityStatus, end_date: date) -> None:
    """Warn on screen and log `gtfs.feed_expiring` / `gtfs.feed_expired` (AC-19)."""
    end = end_date.isoformat()
    if isinstance(status, Expiring):
        log.warning("gtfs.feed_expiring", days_left=status.days_left, end_date=end)
        if status.days_left == 0:
            typer.echo(f"AVISO: el feed caduca hoy ({end})")
        else:
            days = "día" if status.days_left == 1 else "días"
            typer.echo(f"AVISO: el feed caduca en {status.days_left} {days} ({end})")
    elif isinstance(status, Expired):
        log.warning("gtfs.feed_expired", days_ago=status.days_ago, end_date=end)
        days = "día" if status.days_ago == 1 else "días"
        typer.echo(f"AVISO: el feed caducó el {end} (hace {status.days_ago} {days})")


def _echo_direction(report: DirectionReport) -> None:
    typer.echo(
        f"Línea {report.line} · sentido {report.direction_id} · origen: {report.source}"
        f" · viajes: {report.trip_count} · patrones: {len(report.patterns)}"
    )
    first, last = report.first_stop, report.last_stop
    typer.echo(
        f"  Patrón principal {report.main_shape_id}: "
        f"{first.stop_id} {first.name} → {last.stop_id} {last.name}"
    )
    headsigns = "; ".join(f"{headsign} ({count})" for headsign, count in report.headsigns)
    typer.echo(f"  Headsigns: {headsigns}")
    patterns = "; ".join(f"{shape} ({count})" for shape, count in report.patterns)
    typer.echo(f"  Patrones: {patterns}")
