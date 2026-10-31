"""AC-23: a single `.env` at the repository root, overridable by `backend/.env` and the process env.

The backend and the CLI run from `backend/`, so the layout is reproduced with temporary
directories (`root/` and `root/backend/`) and the working directory is moved into `backend/`.
"""

from pathlib import Path

import pytest

from avisabus.config import Settings

FIELDS = ("env", "log_level", "database_url", "public_base_url")


@pytest.fixture
def backend_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for field in FIELDS:
        monkeypatch.delenv(f"AVISABUS_{field.upper()}", raising=False)
    root = tmp_path / "root"
    backend = root / "backend"
    backend.mkdir(parents=True)
    monkeypatch.chdir(backend)
    return backend


def _write_root_env(backend: Path, content: str) -> None:
    (backend.parent / ".env").write_text(content, encoding="utf-8")


def _write_backend_env(backend: Path, content: str) -> None:
    (backend / ".env").write_text(content, encoding="utf-8")


@pytest.mark.spec("project_scaffold.AC-23")
def test_root_dotenv_is_loaded_when_running_from_backend(backend_dir: Path) -> None:
    _write_root_env(
        backend_dir,
        "AVISABUS_ENV=test\nAVISABUS_LOG_LEVEL=DEBUG\nAVISABUS_PUBLIC_BASE_URL=https://root.example\n",
    )
    settings = Settings()
    assert settings.env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.public_base_url == "https://root.example"


@pytest.mark.spec("project_scaffold.AC-23")
def test_backend_dotenv_takes_precedence_over_root_dotenv(backend_dir: Path) -> None:
    _write_root_env(
        backend_dir,
        "AVISABUS_LOG_LEVEL=DEBUG\nAVISABUS_PUBLIC_BASE_URL=https://root.example\n",
    )
    _write_backend_env(backend_dir, "AVISABUS_LOG_LEVEL=WARNING\n")
    settings = Settings()
    assert settings.log_level == "WARNING"  # backend/.env wins
    assert settings.public_base_url == "https://root.example"  # root still fills the rest


@pytest.mark.spec("project_scaffold.AC-23")
def test_process_environment_takes_precedence_over_both_dotenv_files(
    backend_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_root_env(backend_dir, "AVISABUS_LOG_LEVEL=DEBUG\nAVISABUS_ENV=test\n")
    _write_backend_env(backend_dir, "AVISABUS_LOG_LEVEL=WARNING\n")
    monkeypatch.setenv("AVISABUS_LOG_LEVEL", "ERROR")
    monkeypatch.setenv("AVISABUS_ENV", "prod")
    settings = Settings()
    assert settings.log_level == "ERROR"
    assert settings.env == "prod"


@pytest.mark.spec("project_scaffold.AC-23")
def test_defaults_apply_when_no_dotenv_file_exists(backend_dir: Path) -> None:
    settings = Settings()
    assert settings.env == "dev"
    assert settings.log_level == "INFO"
