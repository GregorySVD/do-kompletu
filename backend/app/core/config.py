from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"
DEVELOPMENT_JWT_SECRET = "change-me-in-development"
UNSAFE_JWT_SECRETS = {
    DEVELOPMENT_JWT_SECRET,
    "replace-me-with-a-long-random-secret",
}
PRODUCTION_JWT_SECRET_MIN_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Configuration must behave the same for FastAPI and Alembic, regardless
        # of whether the command was started from the repository or backend root.
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        enable_decoding=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    app_name: str = "Do Kompletu API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str
    jwt_secret: str = DEVELOPMENT_JWT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    activity_confirmation_open_minutes_before: int = Field(default=60, gt=0, le=525600)
    activity_confirmation_deadline_minutes_before: int = Field(
        default=30, ge=0, le=525600
    )
    activity_late_confirmation_grace_minutes: int = Field(default=10, gt=0, le=525600)
    participation_lifecycle_worker_enabled: bool = True
    participation_lifecycle_sweep_interval_seconds: float = Field(
        default=60, gt=0, allow_inf_nan=False
    )
    activity_check_in_open_minutes_before: int = Field(default=30, ge=0, le=525600)
    activity_check_in_close_minutes_after: int = Field(default=60, ge=0, le=525600)
    activity_check_in_radius_meters: int = Field(default=150, ge=1, le=100000)
    activity_check_in_max_accuracy_meters: float = Field(
        default=100, gt=0, allow_inf_nan=False
    )
    bootstrap_user_email: str | None = None
    bootstrap_user_display_name: str | None = None
    bootstrap_user_password: str | None = None
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    @model_validator(mode="after")
    def validate_confirmation_timing(self):
        if (
            self.activity_confirmation_open_minutes_before
            <= self.activity_confirmation_deadline_minutes_before
        ):
            raise ValueError(
                "confirmation open minutes must exceed deadline minutes before start"
            )
        return self

    @model_validator(mode="after")
    def validate_production_jwt_secret(self):
        if self.environment == "production":
            normalized_secret = self.jwt_secret.strip()
            if (
                normalized_secret in UNSAFE_JWT_SECRETS
                or len(normalized_secret) < PRODUCTION_JWT_SECRET_MIN_LENGTH
            ):
                raise ValueError(
                    "production jwt_secret must be a non-default secret with at least "
                    f"{PRODUCTION_JWT_SECRET_MIN_LENGTH} characters"
                )
        return self

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("jwt_secret must not be blank")
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: Any) -> list[str]:
        if isinstance(value, list):
            return value
        if not value:
            return []
        if isinstance(value, str):
            stripped_value = value.strip()
            if not stripped_value:
                return []
            if stripped_value.startswith("["):
                return json.loads(stripped_value)
            return [
                origin.strip() for origin in stripped_value.split(",") if origin.strip()
            ]
        raise ValueError(
            "cors_allowed_origins must be a list or comma-separated string"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
