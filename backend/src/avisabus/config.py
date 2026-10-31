"""Application settings loaded from `AVISABUS_*` environment variables and optional `.env` files.

The backend runs from `backend/`, so the repository-root `.env` is read as `../.env`. Priority
(highest first): process environment > `backend/.env` > root `.env` > defaults.
Every variable must be documented in the repository's `.env.example`.
"""

from typing import Literal, Self

import structlog
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from avisabus.domain.models.occupancy import OccupancyThresholds

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

    @model_validator(mode="after")
    def _check_occupancy(self) -> Self:
        """occupancy_sensor AC-03: `0 < medium < full <= 1` and `seats <= capacity`."""
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
        return self

    def occupancy_thresholds(self) -> OccupancyThresholds:
        return OccupancyThresholds(
            medium=self.occupancy_threshold_medium, full=self.occupancy_threshold_full
        )

    @model_validator(mode="after")
    def _check_stop_token_secret(self) -> Self:
        """Production needs a secret of at least 32 bytes; dev/test fall back to a fixed one."""
        configured = _secret_length(self.stop_token_secret)
        if self.env == "prod":
            if configured < MIN_STOP_TOKEN_SECRET_BYTES:
                raise ConfigurationError(
                    "AVISABUS_STOP_TOKEN_SECRET must be set to at least "
                    f"{MIN_STOP_TOKEN_SECRET_BYTES} bytes when AVISABUS_ENV=prod"
                )
        elif configured == 0:
            log.warning("security.dev_stop_token_secret", env=self.env)
        return self

    def stop_token_secret_bytes(self) -> bytes:
        """Secret that signs stop tokens: the configured one or, in dev/test, the fixed one."""
        if self.stop_token_secret is None or not self.stop_token_secret.get_secret_value():
            return DEV_STOP_TOKEN_SECRET
        return self.stop_token_secret.get_secret_value().encode()


def _secret_length(secret: SecretStr | None) -> int:
    """Length in bytes (UTF-8) of the secret; 0 when it is unset or empty."""
    return 0 if secret is None else len(secret.get_secret_value().encode())
