"""`avisabus qr generate (--stop ID ... | --all) [--format svg|png] [--out DIR]`.

stop_tokens_qr design §3: the CLI writes one file per stop and `index.csv` (UTF-8, header
`stop_id,name,url,file`). Exit codes: 0 success, 1 no feed imported, 2 some stop does not exist.
"""

import csv
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.outbound.clock import SystemClock
from avisabus.application.generate_stop_qr_codes import (
    GenerateStopQrCodesCommand,
    QrGenerationResult,
)
from avisabus.config import Settings
from avisabus.domain.errors import NoActiveFeedError
from avisabus.logging import configure_logging

EXIT_NO_FEED = 1
EXIT_MISSING_STOP = 2
INDEX_FILE = "index.csv"
INDEX_HEADER = ("stop_id", "name", "url", "file")

qr_app = typer.Typer(no_args_is_help=True, help="QR codes of the stops.")


class OutputFormat(StrEnum):
    SVG = "svg"
    PNG = "png"


def _container() -> CliContainer:
    settings = Settings()
    configure_logging(settings.log_level)
    return build_cli_container(settings, SystemClock())


@qr_app.command("generate")
def generate(
    stops: Annotated[
        list[str] | None,
        typer.Option("--stop", metavar="ID", help="Stop to generate (repeatable)."),
    ] = None,
    all_stops: Annotated[
        bool, typer.Option("--all", help="Every stop of the active feed.")
    ] = False,
    output_format: Annotated[
        OutputFormat, typer.Option("--format", help="Output format.")
    ] = OutputFormat.SVG,
    out: Annotated[Path, typer.Option("--out", metavar="DIR", help="Output directory.")] = Path(
        "qr"
    ),
) -> None:
    """Generate the QR codes of the stops and their index.csv."""
    if bool(stops) == all_stops:
        raise typer.BadParameter(
            "indica --stop ID (una o varias) o --all, pero no ambas", param_hint="--stop"
        )
    command = GenerateStopQrCodesCommand(
        stop_ids=None if all_stops else stops, format=output_format.value
    )
    container = _container()
    try:
        result = container.generate_stop_qr_codes.execute(command)
    except NoActiveFeedError:
        typer.echo("No hay ningún feed importado. Usa `avisabus gtfs import PATH`.", err=True)
        raise typer.Exit(EXIT_NO_FEED) from None
    finally:
        container.close()
    for stop_id in result.missing_stop_ids:
        typer.echo(f"ERROR: parada {stop_id} no existe", err=True)
    _write(result, out)
    typer.echo(f"QR generados: {len(result.generated)} en {out} (índice: {out / INDEX_FILE})")
    if result.missing_stop_ids:
        raise typer.Exit(EXIT_MISSING_STOP)


def _write(result: QrGenerationResult, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for qr in result.generated:
        (out / qr.filename).write_bytes(qr.content)
    with (out / INDEX_FILE).open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(INDEX_HEADER)
        writer.writerows((qr.stop_id, qr.name, qr.url, qr.filename) for qr in result.generated)
