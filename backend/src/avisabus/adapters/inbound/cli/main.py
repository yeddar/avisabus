"""Command line entry point (`avisabus`). Features add their sub-commands here."""

import typer

from avisabus.adapters.inbound.cli.gtfs import gtfs_app

app = typer.Typer(name="avisabus", no_args_is_help=True)
app.add_typer(gtfs_app, name="gtfs")


@app.callback()
def main() -> None:
    """AvisaBus administration commands."""
