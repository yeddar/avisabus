"""Application settings loaded from `AVISABUS_*` environment variables and optional `.env` files.

The backend runs from `backend/`, so the repository-root `.env` is read as `../.env`. Priority
(highest first): process environment > `backend/.env` > root `.env` > defaults.
Every variable must be documented in the repository's `.env.example`.
"""

import json
from pathlib import Path
from typing import Literal, Self

import structlog
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from avisabus.domain.models.occupancy import OccupancyLevel, OccupancyThresholds
from avisabus.domain.services.occupancy_classifier import override_occupied

DEV_STOP_TOKEN_SECRET = b"avisabus-dev-only-secret-do-not-use!"
"""Fixed stop token secret used in `dev` and `test` when none is configured (never in `prod`)."""

MIN_STOP_TOKEN_SECRET_BYTES = 32

log = structlog.get_logger(__name__)


class ConfigurationError(Exception):
    """The configuration is not valid: the API and the CLI must not start."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AVISABUS_", env_file=("../.env", ".env"), extra="ignore"
    )

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    database_url: str = "sqlite:///../data/avisabus.sqlite"
    public_base_url: str = "http://localhost:5173"
    gtfs_expiry_warning_days: int = Field(default=7, ge=0)
    gtfs_batch_size: int = Field(default=10_000, gt=0)
    occupancy_capacity: int = Field(default=90, gt=0)
    occupancy_seats: int = Field(default=28, ge=0)
    occupancy_seed: str = "avisabus"
    occupancy_threshold_medium: float = 0.50
    occupancy_threshold_full: float = 0.85
    stop_token_secret: SecretStr | None = None
    arrivals_source: Literal["http", "replay"] | None = None
    sae_url_template: str = "https://www.emtvalencia.es/QR.php?sec=est&p={stop_id}"
    sae_timeout_s: float = Field(default=3, gt=0)
    sae_cache_ttl_s: float = Field(default=20, ge=0)
    sae_error_ttl_s: float = Field(default=5, ge=0)
    sae_max_concurrency: int = Field(default=4, ge=1)
    sae_replay_dir: Path = Path("tests/fixtures/sae_recordings/stop_508_peak")
    sae_contact: str = ""
    trip_match_tolerance_min: float = Field(default=10, gt=0)
    scheduled_window_min: float = Field(default=90, gt=0)
    scheduled_per_direction: int = Field(default=2, ge=1)
    direction_overrides_file: str = ""
    direction_min_score: float = Field(default=0.2, ge=0, le=1)

    @model_validator(mode="after")
    def _check_occupancy(self) -> Self:
        """occupancy_sensor AC-03: `0 < medium < full <= 1`, `seats <= capacity` and (v1.1)
        every level admits some whole number of occupied places with the configured capacity."""
        medium, full = self.occupancy_threshold_medium, self.occupancy_threshold_full
        if not 0 < medium < full <= 1:
            raise ConfigurationError(
                "AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM and AVISABUS_OCCUPANCY_THRESHOLD_FULL must "
                f"satisfy 0 < medium < full <= 1 (got medium={medium}, full={full})"
            )
        if self.occupancy_seats > self.occupancy_capacity:
            raise ConfigurationError(
                "AVISABUS_OCCUPANCY_SEATS must not exceed AVISABUS_OCCUPANCY_CAPACITY "
                f"(got seats={self.occupancy_seats}, capacity={self.occupancy_capacity})"
            )
        thresholds = self.occupancy_thresholds()
        for level in OccupancyLevel:
            if override_occupied(level, self.occupancy_capacity, thresholds) is None:
                raise ConfigurationError(
                    f"no whole number of occupied places is {level} with "
                    f"AVISABUS_OCCUPANCY_CAPACITY={self.occupancy_capacity}, "
                    f"AVISABUS_OCCUPANCY_THRESHOLD_MEDIUM={medium} and "
                    f"AVISABUS_OCCUPANCY_THRESHOLD_FULL={full}"
                )
        return self

    def occupancy_thresholds(self) -> OccupancyThresholds:
        return OccupancyThresholds(
            medium=self.occupancy_threshold_medium, full=self.occupancy_threshold_full
        )

    @model_validator(mode="after")
    def _check_sae(self) -> Self:
        """sae_arrivals_source: the URL template must say where the stop goes."""
        try:
            valid = "{stop_id}" in self.sae_url_template and bool(
                self.sae_url_template.format(stop_id="0")
            )
        except (KeyError, IndexError, ValueError):
            valid = False
        if not valid:
            raise ConfigurationError(
                "AVISABUS_SAE_URL_TEMPLATE must contain {stop_id} and no other placeholder"
            )
        return self

    def resolved_arrivals_source(self) -> Literal["http", "replay"]:
        """sae_arrivals_source AC-20: `replay` by default in `test`, `http` in `dev`/`prod`."""
        if self.arrivals_source is not None:
            return self.arrivals_source
        return "replay" if self.env == "test" else "http"

    @model_validator(mode="after")
    def _check_stop_token_secret(self) -> Self:
        """Production needs a secret of at least 32 bytes; dev/test fall back to a fixed one.

        The dev-secret warning is not logged here (logging is not configured yet): the API and
        the CLI call `log_dev_stop_token_secret_warning` right after `configure_logging`.
        """
        configured = _secret_length(self.stop_token_secret)
        if self.env == "prod" and configured < MIN_STOP_TOKEN_SECRET_BYTES:
            raise ConfigurationError(
                "AVISABUS_STOP_TOKEN_SECRET must be set to at least "
                f"{MIN_STOP_TOKEN_SECRET_BYTES} bytes when AVISABUS_ENV=prod"
            )
        return self

    @property
    def uses_dev_stop_token_secret(self) -> bool:
        """True in dev/test when no secret is configured, so the fixed dev secret signs tokens."""
        return self.env != "prod" and _secret_length(self.stop_token_secret) == 0

    def stop_token_secret_bytes(self) -> bytes:
        """Secret that signs stop tokens: the configured one or, in dev/test, the fixed one."""
        if self.stop_token_secret is None or not self.stop_token_secret.get_secret_value():
            return DEV_STOP_TOKEN_SECRET
        return self.stop_token_secret.get_secret_value().encode()


def read_direction_overrides(settings: Settings) -> dict[str, str]:
    """Raw entries `"{line}|{SAE destination}": "{GTFS headsign}"` of
    `AVISABUS_DIRECTION_OVERRIDES_FILE` (stop_arrivals_api design §4); `{}` when it is unset.

    Raises `ConfigurationError` if the file cannot be read or is not a JSON object of strings:
    the entries themselves are checked against the network later (AC-20).
    """
    if not settings.direction_overrides_file:
        return {}
    path = Path(settings.direction_overrides_file)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ConfigurationError(
            f"cannot read the direction overrides file {path} ({type(error).__name__}); "
            "check AVISABUS_DIRECTION_OVERRIDES_FILE"
        ) from None
    if not isinstance(data, dict) or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in data.items()
    ):
        raise ConfigurationError(
            f"the direction overrides file {path} must be a JSON object of strings "
            '("{line}|{SAE destination}": "{GTFS headsign}")'
        )
    return dict(data)


def log_dev_stop_token_secret_warning(settings: Settings) -> None:
    """stop_tokens_qr AC-05: warn, in the configured JSON log, that the dev secret is in use."""
    if settings.uses_dev_stop_token_secret:
        log.warning("security.dev_stop_token_secret", env=settings.env)


def _secret_length(secret: SecretStr | None) -> int:
    """Length in bytes (UTF-8) of the secret; 0 when it is unset or empty."""
    return 0 if secret is None else len(secret.get_secret_value().encode())
