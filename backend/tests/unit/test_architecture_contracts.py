"""Proves that the import-linter contracts in `.importlinter` reject forbidden imports.

Each case copies `src/avisabus` and `.importlinter` to a temporary directory, adds a module with
an import that breaks the hexagonal dependency rule and runs `lint-imports` on the copy.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"


def _run_lint_imports(tmp_path: Path, offender: str | None, statement: str = "") -> int:
    src = tmp_path / "src"
    shutil.copytree(
        BACKEND / "src" / "avisabus",
        src / "avisabus",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    config = tmp_path / ".importlinter"
    shutil.copy(BACKEND / ".importlinter", config)
    if offender is not None:
        module = src / Path(*offender.split(".")).with_suffix(".py")
        module.write_text(f"{statement}\n", encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(src)}
    result = subprocess.run(  # noqa: S603 - fixed executable, controlled arguments
        [str(LINT_IMPORTS), "--config", str(config), "--no-cache"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode


@pytest.mark.spec("project_scaffold.AC-03")
@pytest.mark.spec("project_scaffold.AC-04")
def test_contracts_pass_without_forbidden_imports(tmp_path: Path) -> None:
    assert _run_lint_imports(tmp_path, offender=None) == 0


@pytest.mark.spec("project_scaffold.AC-03")
@pytest.mark.parametrize(
    "statement",
    [
        "import avisabus.application",
        "import avisabus.adapters",
        "import avisabus.background",
        "import fastapi",
        "import pydantic",
        "import pydantic_settings",
        "import httpx",
        "import typer",
        "import structlog",
        "import sqlalchemy",
    ],
)
def test_domain_cannot_import_outer_layers_or_external_libraries(
    tmp_path: Path, statement: str
) -> None:
    code = _run_lint_imports(tmp_path, offender="avisabus.domain.offender", statement=statement)
    assert code != 0


@pytest.mark.spec("project_scaffold.AC-04")
def test_application_cannot_import_adapters(tmp_path: Path) -> None:
    code = _run_lint_imports(
        tmp_path,
        offender="avisabus.application.offender",
        statement="import avisabus.adapters",
    )
    assert code != 0
