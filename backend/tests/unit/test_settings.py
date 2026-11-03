import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from avisabus.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]
FIELDS = ("env", "log_level", "database_url", "public_base_url")


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for field in FIELDS:
        monkeypatch.delenv(f"AVISABUS_{field.upper()}", raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env file from the developer's checkout


@pytest.mark.spec("project_scaffold.AC-09")
def test_defaults_are_safe_for_development() -> None:
    settings = Settings()
    assert settings.env == "dev"
    assert settings.log_level == "INFO"
    assert settings.database_url == "sqlite:///../data/avisabus.sqlite"
    assert settings.public_base_url == "http://localhost:5173"


@pytest.mark.spec("project_scaffold.AC-09")
def test_environment_variables_with_prefix_override_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AVISABUS_ENV", "prod")
    monkeypatch.setenv("AVISABUS_LOG_LEVEL", "WARNING")
    monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", "x" * 32)  # required in prod
    monkeypatch.setenv("AVISABUS_DATABASE_URL", "sqlite:////srv/avisabus.sqlite")
    monkeypatch.setenv("AVISABUS_PUBLIC_BASE_URL", "https://avisabus.example")
    settings = Settings()
    assert settings.env == "prod"
    assert settings.log_level == "WARNING"
    assert settings.database_url == "sqlite:////srv/avisabus.sqlite"
    assert settings.public_base_url == "https://avisabus.example"


@pytest.mark.spec("project_scaffold.AC-09")
def test_variables_without_prefix_are_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("ENV", "prod")
    settings = Settings()
    assert settings.log_level == "INFO"
    assert settings.env == "dev"


@pytest.mark.spec("project_scaffold.AC-09")
def test_optional_dotenv_file_is_loaded(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "AVISABUS_ENV=test\nAVISABUS_LOG_LEVEL=DEBUG\nUNRELATED=1\n", encoding="utf-8"
    )
    settings = Settings()
    assert settings.env == "test"
    assert settings.log_level == "DEBUG"


@pytest.mark.spec("project_scaffold.AC-09")
def test_environment_takes_precedence_over_dotenv_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / ".env").write_text("AVISABUS_LOG_LEVEL=DEBUG\n", encoding="utf-8")
    monkeypatch.setenv("AVISABUS_LOG_LEVEL", "ERROR")
    assert Settings().log_level == "ERROR"


@pytest.mark.spec("project_scaffold.AC-09")
def test_unknown_environment_name_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVISABUS_ENV", "staging")
    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.spec("project_scaffold.AC-09")
def test_env_example_documents_every_setting() -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*(AVISABUS_[A-Z0-9_]+)=", example, flags=re.MULTILINE))
    expected = {f"AVISABUS_{name.upper()}" for name in Settings.model_fields}
    assert documented == expected
