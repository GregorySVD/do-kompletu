from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ActivityCategoryId(StrEnum):
    TEAM_SPORT = "623c6216-f59e-4167-a238-bfda04d99488"
    BOARD_GAMES = "8e50d1b3-0b2e-4988-a4b6-e824cc12835b"
    RPG = "27cced11-fefa-4ff1-8658-ac5550bc58e8"
    GAMING = "cf0e7c10-837d-4868-bb16-4eed38feead1"
    STUDY = "ced1fc24-49a0-4b37-b5f0-2eec13c082cb"
    TECHNOLOGY = "1e3de603-e9fa-432c-8634-6e1298e53bf3"
    MUSIC = "0b3903dd-849f-478c-a7e4-225707ac41af"
    CREATIVE = "6fe86e3d-d037-426e-8c1d-c86a283304be"


class PriceType(StrEnum):
    FREE = "FREE"
    PAID = "PAID"


class ActivityStatus(StrEnum):
    PUBLISHED = "PUBLISHED"
    ONGOING = "ONGOING"
    ENDED = "ENDED"


@dataclass(frozen=True, slots=True)
class ActivityCategoryDefinition:
    id: ActivityCategoryId
    name: str
    slug: str


ACTIVITY_CATEGORIES = {
    category.id: category
    for category in (
        ActivityCategoryDefinition(
            ActivityCategoryId.TEAM_SPORT,
            "Sport zespołowy",
            "sport-zespolowy",
        ),
        ActivityCategoryDefinition(
            ActivityCategoryId.BOARD_GAMES,
            "Gry planszowe",
            "gry-planszowe",
        ),
        ActivityCategoryDefinition(ActivityCategoryId.RPG, "RPG", "rpg"),
        ActivityCategoryDefinition(
            ActivityCategoryId.GAMING,
            "Gaming",
            "gaming",
        ),
        ActivityCategoryDefinition(
            ActivityCategoryId.STUDY,
            "Wspólna nauka",
            "wspolna-nauka",
        ),
        ActivityCategoryDefinition(
            ActivityCategoryId.TECHNOLOGY,
            "Technologia",
            "technologia",
        ),
        ActivityCategoryDefinition(
            ActivityCategoryId.MUSIC,
            "Muzyka",
            "muzyka",
        ),
        ActivityCategoryDefinition(
            ActivityCategoryId.CREATIVE,
            "Kreatywne",
            "kreatywne",
        ),
    )
}
ACTIVITY_CATEGORIES_BY_SLUG = {
    category.slug: category for category in ACTIVITY_CATEGORIES.values()
}

ACTIVITY_CREATE_EXAMPLE = {
    "title": "Siatkówka na Orliku",
    "description": "Amatorski mecz siatkówki dla każdego chętnego.",
    "category_id": ActivityCategoryId.TEAM_SPORT.value,
    "start_at": "2030-08-08T16:00:00Z",
    "end_at": "2030-08-08T18:00:00Z",
    "location_name": "Orlik przy ul. Gdańskiej",
    "address": "ul. Gdańska 1, Poznań",
    "latitude": 52.4232,
    "longitude": 16.9461,
    "min_participants": 4,
    "has_participant_limit": True,
    "max_participants": 12,
    "price_type": PriceType.FREE.value,
    "price_amount": None,
}

ACTIVITY_CREATE_EXAMPLES = {
    "valid_free_activity": {
        "summary": "Free activity with a participant limit",
        "description": "A free activity with twelve available participant places.",
        "value": ACTIVITY_CREATE_EXAMPLE,
    },
    "free_unbounded": {
        "summary": "Free activity without a participant limit",
        "description": "An activity with no maximum number of participants.",
        "value": {
            "title": "Wspólna nauka do egzaminu",
            "description": "Wspólna powtórka materiału i rozwiązywanie zadań.",
            "category_id": ActivityCategoryId.STUDY.value,
            "start_at": "2030-09-10T17:00:00+02:00",
            "end_at": "2030-09-10T20:00:00+02:00",
            "location_name": "Biblioteka Główna AGH",
            "address": "al. Mickiewicza 30, Kraków",
            "latitude": 50.0664,
            "longitude": 19.9213,
            "min_participants": 2,
            "has_participant_limit": False,
            "max_participants": None,
            "price_type": PriceType.FREE.value,
            "price_amount": None,
        },
    },
    "paid_bounded": {
        "summary": "Paid activity with a participant limit",
        "description": "A paid workshop with a finite number of places.",
        "value": {
            "title": "Warsztaty ceramiczne",
            "description": "Warsztaty lepienia i szkliwienia dla początkujących.",
            "category_id": ActivityCategoryId.CREATIVE.value,
            "start_at": "2030-10-17T18:00:00+02:00",
            "end_at": "2030-10-17T20:30:00+02:00",
            "location_name": "Pracownia na Kazimierzu",
            "address": "ul. Józefa 12, Kraków",
            "latitude": 50.0523,
            "longitude": 19.945,
            "min_participants": 4,
            "has_participant_limit": True,
            "max_participants": 10,
            "price_type": PriceType.PAID.value,
            "price_amount": 40.0,
        },
    },
}


def _build_category_markdown_table() -> str:
    rows = [
        "| Category | `category_id` | Slug |",
        "| --- | --- | --- |",
    ]
    rows.extend(
        f"| {category.name} | `{category.id}` | `{category.slug}` |"
        for category in ACTIVITY_CATEGORIES.values()
    )
    return "\n".join(rows)


ACTIVITY_CATEGORY_MARKDOWN_TABLE = _build_category_markdown_table()


class ActivityCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [example["value"] for example in ACTIVITY_CREATE_EXAMPLES.values()]
        },
    )

    title: str = Field(
        min_length=3,
        max_length=80,
        description="Short public activity title.",
    )
    description: str = Field(
        min_length=10,
        max_length=1000,
        description="Public activity description.",
    )
    category_id: ActivityCategoryId = Field(
        description=(
            "Use one of the category IDs listed above or returned by "
            "`GET /api/v1/categories`."
        )
    )
    start_at: datetime = Field(
        description="Timezone-aware activity start. Must be earlier than `end_at`."
    )
    end_at: datetime = Field(
        description="Timezone-aware activity end. Must be later than `start_at`."
    )
    location_name: str = Field(
        min_length=1,
        max_length=120,
        description="Human-readable venue name.",
    )
    address: str = Field(
        min_length=1,
        max_length=300,
        description="Human-readable street or venue address.",
    )
    latitude: float = Field(
        ge=-90,
        le=90,
        description="WGS 84 latitude in the inclusive range -90 to 90.",
    )
    longitude: float = Field(
        ge=-180,
        le=180,
        description="WGS 84 longitude in the inclusive range -180 to 180.",
    )
    min_participants: int = Field(
        ge=2,
        le=100,
        description="Minimum desired number of participants, from 2 to 100.",
    )
    has_participant_limit: bool = Field(
        default=False,
        description=(
            "When false, `max_participants` must be null. When true, a maximum "
            "greater than or equal to `min_participants` is required."
        ),
    )
    max_participants: int | None = Field(
        default=None,
        ge=2,
        le=100,
        description=(
            "Maximum participants when has_participant_limit is true (2 to 100 and "
            "at least min_participants), or null when the activity has no limit."
        ),
    )
    price_type: PriceType = Field(
        description=(
            "FREE means participation costs nothing and `price_amount` must be "
            "null. PAID requires a positive `price_amount`."
        )
    )
    price_amount: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=10,
        decimal_places=2,
        description=(
            "Price in PLN for PAID activities. Must be null for FREE activities."
        ),
    )

    @field_validator("title", "description", "location_name", "address", mode="before")
    @classmethod
    def strip_text_fields(cls, value: Any) -> Any:
        return value.strip() if isinstance(value, str) else value

    @field_validator("start_at", "end_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("datetime must include a timezone offset")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_business_rules(self) -> ActivityCreate:
        if self.end_at <= self.start_at:
            raise ValueError("end_at must be later than start_at")

        if self.has_participant_limit:
            if self.max_participants is None:
                raise ValueError(
                    "max_participants is required when has_participant_limit is true"
                )
            if self.max_participants < self.min_participants:
                raise ValueError(
                    "max_participants must be greater than or equal to min_participants"
                )
        elif self.max_participants is not None:
            raise ValueError(
                "max_participants must be null when has_participant_limit is false"
            )

        if self.price_type == PriceType.FREE and self.price_amount is not None:
            raise ValueError("price_amount must be null for a FREE activity")
        if self.price_type == PriceType.PAID and self.price_amount is None:
            raise ValueError("price_amount is required for a PAID activity")

        return self


class ActivityCategoryRead(BaseModel):
    id: UUID = Field(description="Stable category identifier used by ActivityCreate.")
    name: str = Field(description="Human-readable category name.")
    slug: str = Field(description="Stable machine-readable category slug.")


class ActivityOrganizerRead(BaseModel):
    id: UUID = Field(description="Public identifier of the activity organizer.")
    display_name: str = Field(description="Organizer display name safe for public display.")
    avatar_url: str | None = Field(description="Organizer avatar URL, when configured.")


class ActivityTagRead(BaseModel):
    id: UUID = Field(description="Stable tag identifier.")
    name: str = Field(description="Human-readable tag name.")
    slug: str = Field(description="Machine-readable tag slug.")


class ActivityPermissionsRead(BaseModel):
    can_edit: bool = Field(
        default=False,
        description="Whether the current user may edit the activity; currently always false.",
    )
    can_delete: bool = Field(
        default=False,
        description="Whether the current user may delete the activity; currently always false.",
    )
    can_join: bool = Field(
        default=False,
        description="Whether the current user may join the activity; currently always false.",
    )
    can_leave: bool = Field(
        default=False,
        description="Whether the current user may leave the activity; currently always false.",
    )
    can_confirm: bool = Field(
        default=False,
        description="Whether the current user may confirm attendance; currently always false.",
    )
    can_check_in: bool = Field(
        default=False,
        description="Whether the current user may check in; currently always false.",
    )
    can_view_gallery: bool = Field(
        default=False,
        description="Whether the current user may view the gallery; currently always false.",
    )
    can_upload_photo: bool = Field(
        default=False,
        description="Whether the current user may upload a photo; currently always false.",
    )


class ActivityListItem(BaseModel):
    id: UUID
    title: str
    category: ActivityCategoryRead
    start_at: datetime
    end_at: datetime
    location_name: str
    address: str
    latitude: float
    longitude: float
    distance_m: float | None = Field(
        default=None,
        description=(
            "Distance from the querying user in metres; currently null until nearby "
            "search is implemented."
        ),
    )
    price_type: PriceType
    min_participants: int
    max_participants: int | None
    participant_count: int = Field(
        description="Confirmed participant count; currently 0 until participation is implemented."
    )
    checked_in_count: int = Field(
        description="Checked-in count; currently 0 until check-in is implemented."
    )
    waitlist_count: int = Field(
        description="Waitlist count; currently 0 until waitlists are implemented."
    )
    available_slots: int | None = Field(
        description=(
            "Derived capacity remaining (max_participants minus participant_count), "
            "or null for an activity without a participant limit."
        )
    )
    status: ActivityStatus = Field(
        description=(
            "Time-derived status: PUBLISHED before start_at, ONGOING from start_at "
            "until end_at, and ENDED afterward."
        )
    )


class ActivityRead(ActivityListItem):
    description: str = Field(description="Organizer-provided activity description.")
    organizer: ActivityOrganizerRead = Field(
        description="Public, safe organizer information."
    )
    tags: list[ActivityTagRead] = Field(
        default_factory=list,
        description="Activity tags; currently returned as an empty list.",
    )
    confirmation_opens_at: datetime | None = Field(
        default=None,
        description="Reserved confirmation-window start; currently null.",
    )
    confirmation_deadline_at: datetime | None = Field(
        default=None,
        description="Reserved confirmation deadline; currently null.",
    )
    checkin_opens_at: datetime | None = Field(
        default=None,
        description="Reserved check-in-window start; currently null.",
    )
    checkin_closes_at: datetime | None = Field(
        default=None,
        description="Reserved check-in-window end; currently null.",
    )
    checkin_radius_m: int | None = Field(
        default=None,
        description="Reserved geographic check-in radius; currently null.",
    )
    price_amount: float | None = Field(
        description="Price in PLN for PAID activities, otherwise null."
    )
    currency: str | None = Field(
        description="Currency code for paid activities (`PLN`), otherwise null."
    )
    current_user_participation: None = Field(
        default=None,
        description="Reserved participation state for the current user; currently null.",
    )
    permissions: ActivityPermissionsRead = Field(
        default_factory=ActivityPermissionsRead,
        description="Current user's permissions; all values are currently false.",
    )
