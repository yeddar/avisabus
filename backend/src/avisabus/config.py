"""Application settings loaded from `AVISABUS_*` environment variables and optional `.env` files.

The backend runs from `backend/`, so the repository-root `.env` is read as `../.env`. Priority
(highest first): process environment > `backend/.env` > root `.env` > defaults.
Every variable must be documented in the repository's `.env.example`.
"""

from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from avisabus.domain.models.occupancy import OccupancyThresholds


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
