from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(description="User UUID.")
    email: EmailStr = Field(description="Normalized account email address.")
    display_name: str = Field(
        description=(
            "Case-insensitively unique public username with the user's chosen "
            "capitalization preserved."
        )
    )
    avatar_url: str | None = Field(description="Optional public avatar URL.")
    points_total: int = Field(description="Current accumulated points.")
    is_active: bool = Field(description="Whether the account may authenticate.")
    created_at: datetime = Field(description="Timezone-aware account creation time.")


class UserUpdate(BaseModel):
    display_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=80,
        description=(
            "New public username. Surrounding whitespace is removed, comparison is "
            "case-insensitive, and chosen capitalization is preserved."
        ),
    )
    avatar_url: str | None = Field(
        default=None,
        max_length=2048,
        description="New public avatar URL, or null to clear it.",
    )

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized_value = value.strip()
        if not normalized_value:
            raise ValueError("display_name must not be blank")
        return normalized_value
