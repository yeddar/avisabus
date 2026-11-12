"""Production template `deploy/.env.prod.example` (deployment_rpi AC-08).

`.env.example` (development) is checked by `test_settings.py` (project_scaffold AC-09)."""

import re
import subprocess
from pathlib import Path

import pytest

from avisabus.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]
PROD_EXAMPLE = REPO_ROOT / "deploy" / ".env.prod.example"
ASSIGNMENT = re.compile(r"^(#?)\s*(AVISABUS_[A-Z0-9_]+)=(.*)$", flags=re.MULTILINE)


def _assignments() -> dict[str, tuple[bool, str]]:
    """`{variable: (commented out, value without trailing comment)}`."""
    text = PROD_EXAMPLE.read_text(encoding="utf-8")
    return {
        name: (bool(comment), value.split(" #", 1)[0].strip())
        for comment, name, value in ASSIGNMENT.findall(text)
    }


@pytest.mark.spec("deployment_rpi.AC-08")
def test_the_production_template_documents_every_setting() -> None:
    expected = {f"AVISABUS_{name.upper()}" for name in Settings.model_fields}
    assert set(_assignments()) == expected


@pytest.mark.spec("deployment_rpi.AC-08")
def test_the_production_template_is_set_for_production() -> None:
    values = {name: value for name, (commented, value) in _assignments().items() if not commented}
    assert values["AVISABUS_ENV"] == "prod"
    assert values["AVISABUS_ARRIVALS_SOURCE"] == "http"  # the real SAE, by default
    assert values["AVISABUS_PUBLIC_BASE_URL"].startswith("https://")
    # Mandatory values are placeholders the operator must fill in.
    for name in ("AVISABUS_STOP_TOKEN_SECRET", "AVISABUS_SAE_CONTACT"):
        assert name in values
    # Paths are absolute inside the container.
    assert values["AVISABUS_DATABASE_URL"] == "sqlite:////data/avisabus.sqlite"
    assert values["AVISABUS_SAE_REPLAY_DIR"] == "/app/replay/stop_508_peak"
    assert values["AVISABUS_DIRECTION_OVERRIDES_FILE"] == ""


@pytest.mark.spec("deployment_rpi.AC-08")
def test_the_production_template_explains_the_secret_and_the_replay_switch() -> None:
    text = PROD_EXAMPLE.read_text(encoding="utf-8")
    assert "secrets.token_urlsafe(48)" in text
    assert "AVISABUS_ARRIVALS_SOURCE=replay" in text


@pytest.mark.spec("deployment_rpi.AC-08")
def test_the_real_production_file_is_ignored_by_git() -> None:
    result = subprocess.run(  # noqa: S603 - fixed command
        ["git", "check-ignore", "--no-index", "-q", "deploy/.env.prod"],  # noqa: S607
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 0, "deploy/.env.prod is not in .gitignore"


def test_the_template_itself_is_not_ignored() -> None:
    result = subprocess.run(  # noqa: S603 - fixed command
        ["git", "check-ignore", "--no-index", "-q", "deploy/.env.prod.example"],  # noqa: S607
        cwd=REPO_ROOT,
        check=False,
    )
    assert result.returncode == 1
