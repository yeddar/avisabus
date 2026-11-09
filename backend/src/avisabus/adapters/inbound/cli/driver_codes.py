"""`avisabus driver-codes create | list | revoke` (driver_codes_cli design §4, CU-13).

The plain code is printed once, by `create`, and is never logged (AC-03).

Exit codes: 0 success (also revoking a revoked code), 1 unknown `code_id` or no free code after
the retries, 2 invalid label.
"""

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Annotated, Any, NoReturn

import typer

from avisabus.adapters.inbound.cli.container import CliContainer, build_cli_container
from avisabus.adapters.outbound.clock import SystemClock
from avisabus.config import Settings
from avisabus.domain.errors import (
    DriverCodeAlreadyRevokedError,
    DriverCodeCollisionError,
    DriverCodeNotFoundError,
    InvalidDriverCodeLabelError,
)
from avisabus.domain.models.driver import DriverCode
from avisabus.logging import configure_logging

EXIT_FAILURE = 1
EXIT_INVALID_LABEL = 2
STATUS_ACTIVE = "activo"
STATUS_REVOKED = "revocado"
TABLE_HEADER = ("CODE_ID", "ETIQUETA", "CREADO", "ESTADO", "TURNO")
INVALID_LABEL_MESSAGE = (
    "ERROR: la etiqueta es obligatoria (--label) y debe tener de 1 a 40 caracteres imprimibles, "
    "sin saltos de línea."
)

driver_codes_app = typer.Typer(no_args_is_help=True, help="Driver access codes.")


def _container(*, logs_to_stderr: bool = False) -> CliContainer:
    settings = Settings()
    configure_logging(settings.log_level)
    if logs_to_stderr:
        _send_logs_to_stderr()
    return build_cli_container(settings, SystemClock())


def _send_logs_to_stderr() -> None:
    """`configure_logging` writes to stdout, where machine-readable output must stand alone."""
    for handler in logging.getLogger().handlers:
        if isinstance(handler, logging.StreamHandler) and handler.stream is sys.stdout:
            handler.setStream(sys.stderr)


@driver_codes_app.command("create")
def create(
    label: Annotated[
        str | None,
        typer.Option("--label", help="Free text, 1 to 40 printable characters (required)."),
    ] = None,
) -> None:
    """Create a driver code and print it, only this once."""
    if label is None:
        _invalid_label()
    container = _container()
    try:
        created = container.create_driver_code.execute(label)
    except InvalidDriverCodeLabelError:
        _invalid_label()
    except DriverCodeCollisionError:
        typer.echo("ERROR: no se ha podido generar un código libre. Inténtalo de nuevo.", err=True)
        raise typer.Exit(EXIT_FAILURE) from None
    finally:
        container.close()
    plain = created.plain_code
    typer.echo(f"Código creado: {created.code.code_id}  ·  {created.code.label}")
    typer.echo(f"  Código de acceso: {plain[:4]} {plain[4:]}")
    typer.echo("  Apúntalo ahora: no se volverá a mostrar.")


@driver_codes_app.command("list")
def list_codes(
    as_json: Annotated[bool, typer.Option("--json", help="Print the list as JSON.")] = False,
) -> None:
    """List the driver codes, without the codes themselves."""
    container = _container(logs_to_stderr=as_json)
    try:
        codes = container.list_driver_codes.execute()
    finally:
        container.close()
    if as_json:
        typer.echo(json.dumps(_as_json(codes), ensure_ascii=False, indent=2))
    elif codes:
        typer.echo(_as_table(codes))
    else:
        typer.echo("No hay códigos de conductor.")


@driver_codes_app.command("revoke")
def revoke(
    code_id: Annotated[str, typer.Argument(help="Identifier of the code, e.g. dc-k3m9qa.")],
) -> None:
    """Revoke a driver code."""
    container = _container()
    try:
        _code, had_open_session = container.revoke_driver_code.execute(code_id)
    except DriverCodeNotFoundError as error:
        typer.echo(f"ERROR: el código {error.code_id} no existe", err=True)
        raise typer.Exit(EXIT_FAILURE) from None
    except DriverCodeAlreadyRevokedError as error:
        typer.echo(
            f"AVISO: el código {error.code_id} ya estaba revocado "
            f"desde {_minutes(error.revoked_at)}.",
            err=True,
        )
        return
    finally:
        container.close()
    detail = (
        "Tenía un turno abierto: se cerrará en menos de 1 minuto."
        if had_open_session
        else "No tenía ningún turno abierto."
    )
    typer.echo(f"Código {code_id} revocado. {detail}")


def _invalid_label() -> NoReturn:
    typer.echo(INVALID_LABEL_MESSAGE, err=True)
    raise typer.Exit(EXIT_INVALID_LABEL)


def _status(code: DriverCode) -> str:
    return STATUS_REVOKED if code.revoked else STATUS_ACTIVE


def _minutes(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def _as_json(codes: list[tuple[DriverCode, bool]]) -> list[dict[str, Any]]:
    return [
        {
            "code_id": code.code_id,
            "label": code.label,
            "created_at": code.created_at.astimezone(UTC).isoformat(),
            "status": _status(code),
            "has_open_session": has_open_session,
        }
        for code, has_open_session in codes
    ]


def _as_table(codes: list[tuple[DriverCode, bool]]) -> str:
    rows = [TABLE_HEADER] + [
        (
            code.code_id,
            code.label,
            _minutes(code.created_at),
            _status(code),
            "sí" if has_open_session else "no",
        )
        for code, has_open_session in codes
    ]
    widths = [max(len(row[column]) for row in rows) for column in range(len(TABLE_HEADER))]
    return "\n".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        for row in rows
    )
