from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_FORECAST_MIN_POINTS = 7
DEFAULT_MAX_SERIES_POINTS = 2000
DEFAULT_MAX_PREDICTION_LENGTH = 30
MINIMUM_SETTING_VALUE = 1


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        populate_by_name=True,
    )

    api_docs_enabled: bool = Field(default=True, validation_alias="API_DOCS_ENABLED")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )
    forecast_min_points: int = Field(
        default=DEFAULT_FORECAST_MIN_POINTS,
        ge=MINIMUM_SETTING_VALUE,
        validation_alias="FORECAST_MIN_POINTS",
    )
    max_series_points: int = Field(
        default=DEFAULT_MAX_SERIES_POINTS,
        ge=MINIMUM_SETTING_VALUE,
        validation_alias="MAX_SERIES_POINTS",
    )
    max_prediction_length: int = Field(
        default=DEFAULT_MAX_PREDICTION_LENGTH,
        ge=MINIMUM_SETTING_VALUE,
        validation_alias="MAX_PREDICTION_LENGTH",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
