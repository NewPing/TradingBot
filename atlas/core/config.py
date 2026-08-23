"""System configuration loaded from environment variables and .env file."""

from decimal import Decimal
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from atlas.core.errors import ConfigurationError


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime
    atlas_env: Literal["dev", "research", "live"] = "dev"
    atlas_log_level: str = "INFO"
    atlas_log_format: Literal["console", "json"] = "console"
    atlas_tz_display: str = "Europe/Berlin"

    # Safety Invariants
    atlas_allow_live: bool = Field(
        default=False,
        description="Hard safety gate. Must remain false in code.",
    )
    atlas_allow_short: bool = False
    atlas_max_leverage: float = 1.0
    atlas_holdout_locked: bool = True

    # Capital & Portfolio
    atlas_virtual_capital_usd: Decimal = Decimal("100000")
    atlas_bucket_alloc: str = "CORE:0.50,SWING:0.30,MOONSHOT:0.15,CASH:0.05"

    # Storage
    atlas_db_url: str = "postgresql+psycopg://atlas:atlas_dev_password@localhost:5432/atlas"
    atlas_redis_url: str = "redis://localhost:6379/0"
    atlas_data_dir: str = "./data"
    atlas_snapshot_dir: str = "./data/snapshots"

    # Providers
    tiingo_api_key: str | None = None
    alpaca_api_key_id: str | None = None
    alpaca_api_secret: str | None = None
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    fmp_api_key: str | None = None
    polygon_api_key: str | None = None

    # LLM Inference
    atlas_llm_base_url: str = "http://192.168.0.149:8080/v1"
    atlas_llm_model: str = "Qwen3.8-27B-Q4"
    atlas_llm_prompt_version: str = "v1.0"

    # Alerting
    atlas_alert_email: str | None = None
    atlas_smtp_url: str | None = None
    atlas_ntfy_topic: str | None = None

    # API / Web
    atlas_api_host: str = "0.0.0.0"
    atlas_api_port: int = 8001
    atlas_session_secret: str = "dev_session_secret_replace_in_production"
    next_public_api_url: str = "http://localhost:8001"

    @field_validator("atlas_max_leverage")
    @classmethod
    def validate_leverage(cls, v: float) -> float:
        if v > 1.0:
            raise ConfigurationError(
                f"Hard invariant D18 violated: ATLAS_MAX_LEVERAGE cannot exceed 1.0 (configured: {v})"
            )
        return v


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
