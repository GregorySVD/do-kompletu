from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.activity import (
    ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    ActivityCategoryId,
    ActivityCreate,
    ActivityPermissionsRead,
    PriceType,
)


class ActivityUpdate(BaseModel):
    """Only explicitly supplied fields are applied; merged state uses ActivityCreate."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        min_length=3,
        max_length=80,
        description="Public title; omitted means unchanged.",
    )
    description: str | None = Field(
        default=None, min_length=10, max_length=1000, description="Public description."
    )
    category_id: ActivityCategoryId | None = Field(
        default=None, description="Canonical category UUID from GET /categories."
    )
    start_at: datetime | None = Field(
        default=None,
        description="Timezone-aware start; must remain strictly in the future.",
    )
    end_at: datetime | None = Field(
        default=None, description="Timezone-aware end, later than the merged start."
    )
    location_name: str | None = Field(
        default=None, min_length=1, max_length=120, description="Display venue name."
    )
    address: str | None = Field(
        default=None,
        min_length=1,
        max_length=300,
        description="Display street/venue address.",
    )
    latitude: float | None = Field(
        default=None,
        ge=-90,
        le=90,
        description="WGS 84 latitude; omitted longitude stays unchanged.",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180,
        le=180,
        description="WGS 84 longitude; omitted latitude stays unchanged.",
    )
    min_participants: int | None = Field(
        default=None,
        ge=2,
        le=100,
        description="Desired minimum; merged maximum must be at least this value.",
    )
    has_participant_limit: bool | None = Field(
        default=None,
        description="False requires merged max_participants=null; true requires a maximum.",
    )
    max_participants: int | None = Field(
        default=None,
        ge=2,
        le=100,
        description="Finite maximum or explicit null when disabling the limit; cannot be below membership count.",
    )
    price_type: PriceType | None = Field(
        default=None,
        description="FREE requires merged price_amount=null; PAID requires a positive amount.",
    )
    price_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
        description="PLN amount, or explicit null when switching to FREE.",
    )

    @field_validator("title", "description", "location_name", "address", mode="before")
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return ActivityCreate.strip_text_fields(value)

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        return ActivityCreate.require_timezone(value) if value is not None else None

    @model_validator(mode="after")
    def validate_supplied_fields(self) -> ActivityUpdate:
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")
        for name in self.model_fields_set - {"max_participants", "price_amount"}:
            if getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


ACTIVITY_PATCH_EXAMPLES = {
    "text": {
        "summary": "Change title and description",
        "value": {
            "title": "Evening volleyball",
            "description": "A friendly volleyball match for all skill levels.",
        },
    },
    "schedule": {
        "summary": "Move the activity in time",
        "value": {"start_at": "2030-08-09T16:00:00Z", "end_at": "2030-08-09T18:00:00Z"},
    },
    "location": {
        "summary": "Change venue and coordinates",
        "value": {
            "location_name": "Poznan sports centre",
            "address": "ul. Piotrowo 2, Poznan",
            "latitude": 52.4005,
            "longitude": 16.9516,
        },
    },
    "capacity": {
        "summary": "Set a finite participant limit",
        "value": {
            "min_participants": 2,
            "has_participant_limit": True,
            "max_participants": 9,
        },
    },
    "unlimited": {
        "summary": "Remove the participant limit",
        "value": {"has_participant_limit": False, "max_participants": None},
    },
    "paid": {
        "summary": "Switch from FREE to PAID",
        "value": {"price_type": "PAID", "price_amount": 25.50},
    },
    "free": {
        "summary": "Switch from PAID to FREE",
        "value": {"price_type": "FREE", "price_amount": None},
    },
}
ACTIVITY_PATCH_RESPONSE_EXAMPLE = {
    **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    "title": "Evening volleyball",
    "description": "A friendly volleyball match for all skill levels.",
    "current_user_participation": None,
    "permissions": ActivityPermissionsRead(
        can_edit=True, can_cancel=True, can_view_gallery=True
    ).model_dump(),
}
ACTIVITY_CANCEL_RESPONSE_EXAMPLE = {
    **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    "status": "CANCELLED",
    "cancelled_at": "2030-08-01T12:00:00Z",
    "current_user_participation": None,
    "permissions": ActivityPermissionsRead(can_view_gallery=True).model_dump(),
}
