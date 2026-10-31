"""Application settings loaded from `AVISABUS_*` environment variables (and an optional `.env`).

Every variable must be documented in the repository's `.env.example`.
"""

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AVISABUS_", env_file=".env", extra="ignore")

    env: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    database_url: str = "sqlite:///../data/avisabus.sqlite"
    public_base_url: str = "http://localhost:5173"
