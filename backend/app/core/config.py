from __future__ import annotations

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Central configuration for GridCool backend.

    All secrets/keys must come from environment variables (or a local `.env`).
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "GridCool API"
    DEMO_MODE: bool = True

    # Mongo
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB: str = "gridcool"

    # Integrations (optional in demo mode)
    OPENWEATHER_API_KEY: str | None = None
    TWILIO_ACCOUNT_SID: str | None = None
    TWILIO_AUTH_TOKEN: str | None = None
    TWILIO_FROM_NUMBER: str | None = None

    # Real-time
    WS_BROADCAST_INTERVAL_SECONDS: int = 10

    # ML forecast (Phase 2 foundation; off by default for demo safety)
    USE_ML_FORECAST: bool = False
    ML_ARTIFACT_DIR: str = "artifacts/ml"
    ML_FORECAST_HORIZON_HOURS: int = 12
    ML_DATA_CSV: str = "backend/data/chennai_hourly_load.csv"
    ML_FORECAST_REFRESH_MINUTES: int = 15
    AUTO_DISPATCH_ENABLED: bool = True
    AUTO_DISPATCH_COOLDOWN_MINUTES: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()

