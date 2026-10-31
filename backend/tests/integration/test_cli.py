from importlib.metadata import entry_points

import pytest
from typer.testing import CliRunner

from avisabus.adapters.inbound.cli.main import app

runner = CliRunner()


@pytest.mark.spec("project_scaffold.AC-13")
def test_help_is_shown_and_exits_with_zero() -> None:
    result = runner.invoke(app, ["--help"], prog_name="avisabus")
    assert result.exit_code == 0
    assert "Usage: avisabus" in result.output


@pytest.mark.spec("project_scaffold.AC-13")
def test_avisabus_console_script_points_to_the_typer_app() -> None:
    (script,) = entry_points(group="console_scripts", name="avisabus")
    assert script.value == "avisabus.adapters.inbound.cli.main:app"
    assert script.load() is app
