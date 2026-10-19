from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_FORECAST_MIN_POINTS = 7
DEFAULT_CHRONOS_MODEL_ID = "autogluon/chronos-2-small"
DEFAULT_SERIES_TIMEZONE = "America/Bogota"
DEFAULT_MAX_SERIES_POINTS = 2000
DEFAULT_MAX_PREDICTION_LENGTH = 30
DEFAULT_MAX_BODY_KIBIBYTES = 256
KIBIBYTE = 1024
DEFAULT_MAX_BODY_BYTES = DEFAULT_MAX_BODY_KIBIBYTES * KIBIBYTE
MINIMUM_SETTING_VALUE = 1
MIN_SERVICE_TOKEN_BYTES = 32
TOKEN_ENCODING = "utf-8"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        populate_by_name=True,
        env_ignore_empty=True,
    )

    ia_service_token: SecretStr = Field(validation_alias="IA_SERVICE_TOKEN")
    ia_service_token_previous: SecretStr | None = Field(
        default=None,
        validation_alias="IA_SERVICE_TOKEN_PREVIOUS",
    )
    chronos_model_id: str = Field(
        default=DEFAULT_CHRONOS_MODEL_ID,
        min_length=1,
        validation_alias="CHRONOS_MODEL_ID",
    )
    chronos_device: Literal["cpu"] = Field(
        default="cpu",
        validation_alias="CHRONOS_DEVICE",
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
    resample_aggregation: Literal["last", "mean"] = Field(
        default="last",
        validation_alias="RESAMPLE_AGGREGATION",
    )
    series_timezone: str = Field(
        default=DEFAULT_SERIES_TIMEZONE,
        validation_alias="SERIES_TIMEZONE",
    )
    max_body_bytes: int = Field(
        default=DEFAULT_MAX_BODY_BYTES,
        ge=MINIMUM_SETTING_VALUE,
        validation_alias="MAX_BODY_BYTES",
    )

    @field_validator("ia_service_token", "ia_service_token_previous")
    @classmethod
    def require_strong_token(cls, token: SecretStr | None) -> SecretStr | None:
        """Reject service tokens shorter than the minimum length in bytes."""
        if token is not None and (
            len(token.get_secret_value().encode(TOKEN_ENCODING))
            < MIN_SERVICE_TOKEN_BYTES
        ):
            minimum = MIN_SERVICE_TOKEN_BYTES
            raise ValueError(f"El token de servicio necesita al menos {minimum} bytes.")
        return token

    @field_validator("series_timezone")
    @classmethod
    def require_known_timezone(cls, timezone: str) -> str:
        """Reject time zone names that are not in the IANA database."""
        try:
            ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError) as error:
            raise ValueError(f"Zona horaria desconocida: {timezone}.") from error
        return timezone

    @property
    def zone(self) -> ZoneInfo:
        """Time zone that defines where each day of the series starts."""
        return ZoneInfo(self.series_timezone)

    def accepted_service_tokens(self) -> tuple[SecretStr, ...]:
        """Return the current token and, during a rotation, the previous one."""
        if self.ia_service_token_previous is None:
            return (self.ia_service_token,)
        return (self.ia_service_token, self.ia_service_token_previous)


@lru_cache
def get_settings() -> Settings:
    return Settings()
