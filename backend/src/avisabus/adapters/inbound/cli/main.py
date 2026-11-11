"""Command line entry point (`avisabus`). Features add their sub-commands here."""

import typer

from avisabus.adapters.inbound.cli.driver_codes import driver_codes_app
from avisabus.adapters.inbound.cli.gtfs import gtfs_app
from avisabus.adapters.inbound.cli.occupancy import occupancy_app
from avisabus.adapters.inbound.cli.openapi import openapi_app
from avisabus.adapters.inbound.cli.qr import qr_app
from avisabus.adapters.inbound.cli.sae import sae_app
from avisabus.adapters.inbound.cli.simulate import sim_app

app = typer.Typer(name="avisabus", no_args_is_help=True)
app.add_typer(driver_codes_app, name="driver-codes")
app.add_typer(gtfs_app, name="gtfs")
app.add_typer(occupancy_app, name="occupancy")
app.add_typer(openapi_app, name="openapi")
app.add_typer(qr_app, name="qr")
app.add_typer(sae_app, name="sae")
app.add_typer(sim_app, name="simulate")


@app.callback()
def main() -> None:
    """AvisaBus administration commands."""
