from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.schemas._validators import normalize_email


class UserRegister(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "email": "kacper@example.com",
                    "password": "StrongPassword123",
                    "display_name": "Kacper",
                }
            ]
        }
    )

    email: EmailStr = Field(
        description=(
            "Unique authentication email stored in its validated, normalized form."
        )
    )
    password: str = Field(
        min_length=8,
        max_length=128,
        description=(
            "Case-sensitive password containing 8 to 128 characters. It is hashed "
            "by the backend and is never returned by the API."
        ),
    )
    display_name: str = Field(
        min_length=1,
        max_length=80,
        description=(
            "Public username. Surrounding whitespace is removed; uniqueness and "
            "login comparison are case-insensitive, while submitted capitalization "
            "is preserved for display."
        ),
    )

    @field_validator("email", mode="before")
    @classmethod
    def validate_email_address(cls, value: str) -> str:
        return normalize_email(str(value))

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str) -> str:
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("display_name must not be blank")
        return normalized_value


class UserLogin(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "identifier": "Kacper",
                    "password": "StrongPassword123",
                },
                {
                    "identifier": "kacper@example.com",
                    "password": "StrongPassword123",
                },
            ]
        },
    )

    identifier: str = Field(
        min_length=1,
        max_length=320,
        description=(
            "Account email or display name. Surrounding whitespace is removed and "
            "display-name comparison is case-insensitive."
        ),
    )
    password: str = Field(
        min_length=1,
        max_length=128,
        description="Case-sensitive account password.",
    )

    @field_validator("identifier", mode="before")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        normalized_value = str(value).strip()
        if not normalized_value:
            raise ValueError("identifier must not be blank")
        return normalized_value


class RefreshTokenRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"refresh_token": "<refresh-token>"}]}
    )

    refresh_token: str = Field(
        min_length=1,
        description="Refresh JWT previously returned by the JSON login endpoint.",
    )


class TokenPair(BaseModel):
    access_token: str = Field(description="Short-lived JWT used as a bearer token.")
    refresh_token: str = Field(description="Long-lived JWT used to obtain access tokens.")
    token_type: Literal["bearer"] = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str = Field(description="Short-lived JWT used as a bearer token.")
    token_type: Literal["bearer"] = "bearer"
