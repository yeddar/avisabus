"""`avisabus openapi export --out PATH` (passenger_stop_view T-01).

The command must work without a database or network: sockets are disabled by pytest-socket and
the database URL points to a file that must not be created.
"""

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from avisabus.adapters.inbound.cli.main import app
from avisabus.adapters.inbound.http.app import openapi_document

runner = CliRunner()


@pytest.fixture
def untouched_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "must-not-exist" / "avisabus.sqlite"
    monkeypatch.setenv("AVISABUS_DATABASE_URL", f"sqlite:///{db}")
    return db


@pytest.mark.spec("passenger_stop_view.AC-01")
def test_writes_the_openapi_document_without_opening_the_database(
    tmp_path: Path, untouched_db: Path
) -> None:
    out = tmp_path / "api" / "openapi.json"

    result = runner.invoke(app, ["openapi", "export", "--out", str(out)])

    assert result.exit_code == 0, result.output
    document = json.loads(out.read_text(encoding="utf-8"))
    assert document == openapi_document()
    assert not untouched_db.exists()
    assert not untouched_db.parent.exists()
    assert "avisabus.main" not in sys.modules


@pytest.mark.spec("passenger_stop_view.AC-01")
def test_document_describes_the_stop_endpoints(tmp_path: Path, untouched_db: Path) -> None:
    out = tmp_path / "openapi.json"

    runner.invoke(app, ["openapi", "export", "--out", str(out)])

    document = json.loads(out.read_text(encoding="utf-8"))
    assert set(document["paths"]) >= {
        "/api/v1/health",
        "/api/v1/stops/{stop_id}",
        "/api/v1/stops/{stop_id}/arrivals",
    }
    schemas = document["components"]["schemas"]
    assert {"StopResponse", "StopArrivalsResponse", "ArrivalSchema", "ProblemSchema"} <= set(
        schemas
    )


@pytest.mark.spec("passenger_stop_view.AC-01")
def test_output_is_stable_indented_sorted_and_ends_with_a_newline(
    tmp_path: Path, untouched_db: Path
) -> None:
    first, second = tmp_path / "a.json", tmp_path / "b.json"

    runner.invoke(app, ["openapi", "export", "--out", str(first)])
    runner.invoke(app, ["openapi", "export", "--out", str(second)])

    text = first.read_text(encoding="utf-8")
    assert text == second.read_text(encoding="utf-8")
    expected = json.dumps(openapi_document(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    assert text == expected


@pytest.mark.spec("passenger_stop_view.AC-01")
def test_does_not_need_a_valid_runtime_configuration(
    tmp_path: Path, untouched_db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # In prod a stop token secret is mandatory; the schema does not depend on it.
    monkeypatch.setenv("AVISABUS_ENV", "prod")
    out = tmp_path / "openapi.json"

    result = runner.invoke(app, ["openapi", "export", "--out", str(out)])

    assert result.exit_code == 0, result.output
    assert out.is_file()
