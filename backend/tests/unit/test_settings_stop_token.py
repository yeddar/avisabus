from pathlib import Path

import pytest
from structlog.testing import capture_logs

from avisabus.config import DEV_STOP_TOKEN_SECRET, ConfigurationError, Settings

VALID_SECRET = "x" * 32


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    for name in ("AVISABUS_ENV", "AVISABUS_STOP_TOKEN_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


@pytest.mark.spec("stop_tokens_qr.AC-04")
@pytest.mark.parametrize("secret", [None, "", "x" * 31, "ñ" * 15])
def test_prod_refuses_to_start_without_a_valid_secret(
    monkeypatch: pytest.MonkeyPatch, secret: str | None
) -> None:
    monkeypatch.setenv("AVISABUS_ENV", "prod")
    if secret is not None:
        monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", secret)
    with pytest.raises(ConfigurationError, match="AVISABUS_STOP_TOKEN_SECRET"):
        Settings()


@pytest.mark.spec("stop_tokens_qr.AC-04")
def test_configuration_error_does_not_reveal_the_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AVISABUS_ENV", "prod")
    monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", "short-secret-value")
    with pytest.raises(ConfigurationError) as error:
        Settings()
    assert "short-secret-value" not in str(error.value)


@pytest.mark.spec("stop_tokens_qr.AC-04")
@pytest.mark.parametrize("secret", ["x" * 32, "ñ" * 16])
def test_prod_accepts_a_secret_of_at_least_32_bytes(
    monkeypatch: pytest.MonkeyPatch, secret: str
) -> None:
    monkeypatch.setenv("AVISABUS_ENV", "prod")
    monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", secret)
    with capture_logs() as logs:
        settings = Settings()
    assert settings.stop_token_secret_bytes() == secret.encode()
    assert logs == []


@pytest.mark.spec("stop_tokens_qr.AC-05")
@pytest.mark.parametrize("env", ["dev", "test"])
@pytest.mark.parametrize("secret", [None, ""])
def test_dev_and_test_without_secret_use_the_dev_secret_and_warn(
    monkeypatch: pytest.MonkeyPatch, env: str, secret: str | None
) -> None:
    monkeypatch.setenv("AVISABUS_ENV", env)
    if secret is not None:
        monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", secret)
    with capture_logs() as logs:
        settings = Settings()
    assert settings.stop_token_secret_bytes() == DEV_STOP_TOKEN_SECRET
    assert DEV_STOP_TOKEN_SECRET == b"avisabus-dev-only-secret-do-not-use!"
    assert [entry["event"] for entry in logs] == ["security.dev_stop_token_secret"]
    assert logs[0]["log_level"] == "warning"


@pytest.mark.spec("stop_tokens_qr.AC-05")
def test_dev_with_a_configured_secret_uses_it_without_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AVISABUS_ENV", "dev")
    monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", "my-local-secret")
    with capture_logs() as logs:
        settings = Settings()
    assert settings.stop_token_secret_bytes() == b"my-local-secret"
    assert logs == []


def test_secret_is_masked_in_the_settings_representation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", VALID_SECRET)
    assert VALID_SECRET not in repr(Settings())
