from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        # Configuration must behave the same for FastAPI and Alembic, regardless
        # of whether the command was started from the repository or backend root.
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        enable_decoding=False,
        extra="ignore",
    )

    app_name: str = "Do Kompletu API"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    database_url: str
    jwt_secret: str = "change-me-in-development"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_allowed_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

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
            return [origin.strip() for origin in stripped_value.split(",") if origin.strip()]
        raise ValueError("cors_allowed_origins must be a list or comma-separated string")


@lru_cache
def get_settings() -> Settings:
    return Settings()
