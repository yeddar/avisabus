"""`avisabus openapi export --out PATH` (passenger_stop_view design §2).

Writes the OpenAPI document of the HTTP API without a database, network or valid configuration,
so the frontend can generate its types from it (`npm run gen:api`, ADR-010). The JSON is indented
with 2 spaces, with sorted keys and a final newline, so that diffs are stable.
"""

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from avisabus.adapters.inbound.http.app import openapi_document

openapi_app = typer.Typer(no_args_is_help=True, help="OpenAPI document of the HTTP API.")


def render_openapi(document: dict[str, Any]) -> str:
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


@openapi_app.callback()
def openapi() -> None:
    """OpenAPI document of the HTTP API."""


@openapi_app.command("export")
def export(
    out: Annotated[
        Path, typer.Option("--out", metavar="FILE", dir_okay=False, help="Output JSON file.")
    ],
) -> None:
    """Write the OpenAPI document of the API to FILE."""
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_openapi(openapi_document()), encoding="utf-8")
    typer.echo(f"OpenAPI document written to {out}")
