"""Command line entry point (`avisabus`). Features add their sub-commands here."""

import typer

app = typer.Typer(name="avisabus", no_args_is_help=True)


@app.callback()
def main() -> None:
    """AvisaBus administration commands."""
