"""Production configuration (deployment_rpi AC-07): with `AVISABUS_ENV=prod` the API and the CLI
refuse to start without a SAE contact (when the arrivals source is `http`) or without an
`https://` public URL. Both build `Settings()` before anything else, so the check lives there."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from avisabus.adapters.inbound.cli.main import app as cli
from avisabus.config import ConfigurationError, Settings

SECRET = "s3cr3t-" + "x" * 32
CONTACT = "ops@avisabus.example"
PUBLIC_URL = "https://avisabus.example"
VARIABLES = (
    "AVISABUS_ENV",
    "AVISABUS_STOP_TOKEN_SECRET",
    "AVISABUS_SAE_CONTACT",
    "AVISABUS_PUBLIC_BASE_URL",
    "AVISABUS_ARRIVALS_SOURCE",
)


@pytest.fixture(autouse=True)
def _production(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A valid production environment; each test breaks one thing."""
    for name in VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)  # no stray .env file from the developer's checkout
    monkeypatch.setenv("AVISABUS_ENV", "prod")
    monkeypatch.setenv("AVISABUS_STOP_TOKEN_SECRET", SECRET)
    monkeypatch.setenv("AVISABUS_SAE_CONTACT", CONTACT)
    monkeypatch.setenv("AVISABUS_PUBLIC_BASE_URL", PUBLIC_URL)


@pytest.mark.spec("deployment_rpi.AC-07")
def test_a_complete_production_configuration_starts() -> None:
    settings = Settings()
    assert settings.env == "prod"
    assert settings.resolved_arrivals_source() == "http"


@pytest.mark.spec("deployment_rpi.AC-07")
@pytest.mark.parametrize("source", [None, "http"])
@pytest.mark.parametrize("contact", [None, "", "   "])
def test_prod_with_the_http_source_needs_a_sae_contact(
    monkeypatch: pytest.MonkeyPatch, source: str | None, contact: str | None
) -> None:
    if source is not None:
        monkeypatch.setenv("AVISABUS_ARRIVALS_SOURCE", source)
    if contact is None:
        monkeypatch.delenv("AVISABUS_SAE_CONTACT")
    else:
        monkeypatch.setenv("AVISABUS_SAE_CONTACT", contact)
    with pytest.raises(ConfigurationError, match="AVISABUS_SAE_CONTACT") as error:
        Settings()
    assert SECRET not in str(error.value)


@pytest.mark.spec("deployment_rpi.AC-07")
def test_prod_with_the_replay_source_does_not_need_a_sae_contact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("AVISABUS_ARRIVALS_SOURCE", "replay")
    monkeypatch.delenv("AVISABUS_SAE_CONTACT")
    assert Settings().resolved_arrivals_source() == "replay"


@pytest.mark.spec("deployment_rpi.AC-07")
@pytest.mark.parametrize(
    "url",
    [
        None,
        "http://avisabus.example",
        "HTTP://avisabus.example",
        "avisabus.example",
        "https://",
        "",
    ],
)
def test_prod_needs_an_https_public_base_url(
    monkeypatch: pytest.MonkeyPatch, url: str | None
) -> None:
    if url is None:
        monkeypatch.delenv("AVISABUS_PUBLIC_BASE_URL")  # default: http://localhost:5173
    else:
        monkeypatch.setenv("AVISABUS_PUBLIC_BASE_URL", url)
    with pytest.raises(ConfigurationError, match="AVISABUS_PUBLIC_BASE_URL") as error:
        Settings()
    assert SECRET not in str(error.value)


@pytest.mark.spec("deployment_rpi.AC-07")
def test_the_error_names_every_wrong_variable_without_showing_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AVISABUS_SAE_CONTACT")
    monkeypatch.setenv("AVISABUS_PUBLIC_BASE_URL", "http://avisabus.example")
    with pytest.raises(ConfigurationError) as error:
        Settings()
    message = str(error.value)
    assert "AVISABUS_SAE_CONTACT" in message
    assert "AVISABUS_PUBLIC_BASE_URL" in message
    assert SECRET not in message


@pytest.mark.spec("deployment_rpi.AC-07")
@pytest.mark.parametrize("env", ["dev", "test"])
def test_dev_and_test_need_neither_contact_nor_https(
    monkeypatch: pytest.MonkeyPatch, env: str
) -> None:
    monkeypatch.setenv("AVISABUS_ENV", env)
    monkeypatch.delenv("AVISABUS_SAE_CONTACT")
    monkeypatch.setenv("AVISABUS_PUBLIC_BASE_URL", "http://localhost:5173")
    assert Settings().env == env


@pytest.mark.spec("deployment_rpi.AC-07")
def test_the_cli_does_not_start_with_an_invalid_production_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AVISABUS_SAE_CONTACT")
    result = CliRunner().invoke(cli, ["gtfs", "info"])
    assert isinstance(result.exception, ConfigurationError)
    assert "AVISABUS_SAE_CONTACT" in str(result.exception)
    assert result.exit_code != 0
