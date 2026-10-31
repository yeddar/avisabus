"""Application settings loaded from `AVISABUS_*` environment variables and optional `.env` files.

The backend runs from `backend/`, so the repository-root `.env` is read as `../.env`. Priority
(highest first): process environment > `backend/.env` > root `.env` > defaults.
Every variable must be documented in the repository's `.env.example`.
"""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
