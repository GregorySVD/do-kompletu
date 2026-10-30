from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]


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
    CANCELLED = "CANCELLED"


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
            "examples": [
                example["value"] for example in ACTIVITY_CREATE_EXAMPLES.values()
            ]
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
    latitude: Latitude = Field(
        description="WGS 84 latitude in the inclusive range -90 to 90.",
    )
    longitude: Longitude = Field(
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
    display_name: str = Field(
        description="Organizer display name safe for public display."
    )
    avatar_url: str | None = Field(description="Organizer avatar URL, when configured.")


class ActivityTagRead(BaseModel):
    id: UUID = Field(description="Stable tag identifier.")
    name: str = Field(description="Human-readable tag name.")
    slug: str = Field(description="Machine-readable tag slug.")


class ActivityPermissionsRead(BaseModel):
    can_edit: bool = Field(
        default=False,
        description="True for the organizer before start_at, unless cancelled.",
    )
    can_cancel: bool = Field(
        default=False,
        description="True for the organizer strictly before end_at, unless already cancelled.",
    )
    can_finalize: bool = Field(
        default=False,
        description="True only for the organizer of an ended, uncancelled activity with unresolved JOINED/CONFIRMED/CHECKED_IN attendance.",
    )
    can_delete: bool = Field(
        default=False,
        description="Whether the current user may delete the activity; currently always false.",
    )
    can_join: bool = Field(
        default=False,
        description=(
            "True for authenticated non-organizers with no membership or LEFT, never an expired or final attendance state, while the "
            "activity is PUBLISHED (strictly before start_at) and uncancelled. Full limited activities are eligible: the request may return JOINED or WAITLISTED. This does not guarantee an immediate place."
        ),
    )
    can_leave: bool = Field(
        default=False,
        description="True for a JOINED/CONFIRMED/WAITLISTED non-organizer before end_at, unless cancelled. JOINED must still be before its effective confirmation deadline; overdue leave cannot reset a reservation. Expired states cannot leave. Waitlist leave frees no capacity.",
    )
    can_confirm: bool = Field(
        default=False,
        description="True only for a JOINED non-organizer at/after public opening and strictly before their effective confirmation deadline, unless cancelled/ended. Evaluated even before the periodic sweep updates an overdue row.",
    )
    can_check_in: bool = Field(
        default=False,
        description="True for a CONFIRMED non-organizer inside the check-in window unless cancelled/ended. Allows attempting check-in; submitted accuracy must pass the configured limit and coordinates must pass PostGIS proximity validation.",
    )
    can_view_gallery: bool = Field(
        default=False,
        description="True for authenticated CHECKED_IN/COMPLETED participants or organizer strictly before end_at + 72h, including cancelled activities.",
    )
    can_upload_photo: bool = Field(
        default=False,
        description="True for CHECKED_IN/COMPLETED participants strictly before end_at + 72h, unless cancelled. Organizer identity alone grants no upload. Upload also enforces max 3 photos per user/activity.",
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
        description="Active capacity count: JOINED + CONFIRMED + CHECKED_IN. WAITLISTED/LEFT/system-expired/final attendance states and organizer excluded. Overdue JOINED remains counted until a sweep persists expiry."
    )
    checked_in_count: int = Field(
        description="Historical successful check-in count: CHECKED_IN + COMPLETED. CONFIRMED/NO_SHOW do not count."
    )
    waitlist_count: int = Field(
        description="Persisted count of WAITLISTED only. At/after start the worker transitions remaining rows to WAITLIST_EXPIRED, excluding them from this count. Cancellation preserves existing evidence and is skipped by automation."
    )
    available_slots: int | None = Field(
        description=(
            "Derived capacity remaining (max_participants minus participant_count), "
            "or null for an activity without a participant limit."
        )
    )
    status: ActivityStatus = Field(
        description=(
            "CANCELLED whenever cancelled_at is set, regardless of time. Otherwise "
            "PUBLISHED before start_at, ONGOING from start_at until end_at, and ENDED afterward."
        )
    )


class ActivityParticipationRead(BaseModel):
    status: Literal[
        "CONFIRMATION_EXPIRED",
        "WAITLIST_EXPIRED",
        "WAITLISTED",
        "JOINED",
        "CONFIRMED",
        "CHECKED_IN",
        "COMPLETED",
        "NO_SHOW",
    ] = Field(
        default="JOINED",
        description="Caller's private current, expired, or final state. CONFIRMATION_EXPIRED releases an unconfirmed place; WAITLIST_EXPIRED never held a place. Both system states are terminal. WAITLISTED cannot confirm/check in. COMPLETED/NO_SHOW require explicit organizer finalization; LEFT is null current participation.",
    )
    joined_at: datetime | None = Field(
        description="UTC time the caller obtained a place, including promotion. Null for WAITLISTED/WAITLIST_EXPIRED. Preserved for CONFIRMATION_EXPIRED."
    )
    waitlisted_at: datetime | None = Field(
        default=None,
        description="Caller-only UTC queue-entry time for this cycle, preserved after promotion; null for a direct join.",
    )
    waitlist_position: int | None = Field(
        default=None,
        ge=1,
        description="Caller-only 1-based FIFO position by waitlisted_at ASC then user_id ASC; null outside WAITLISTED. A snapshot, not a reserved position.",
    )
    effective_confirmation_deadline_at: datetime | None = Field(
        default=None,
        description="Caller-only deadline for JOINED: normal deadline for early joins; late joins/promotions get configured grace capped at start. Null for other states. Exclusive and derived from the current schedule/configuration.",
    )
    confirmation_expired_at: datetime | None = Field(
        default=None,
        description="UTC sweep time when unconfirmed JOINED became terminal CONFIRMATION_EXPIRED; otherwise null.",
    )
    waitlist_expired_at: datetime | None = Field(
        default=None,
        description="UTC sweep time at/after start when remaining WAITLISTED became terminal WAITLIST_EXPIRED; otherwise null.",
    )
    confirmed_at: datetime | None = Field(
        default=None,
        description="Caller-only UTC confirmation time for this cycle, or null.",
    )
    checked_in_at: datetime | None = Field(
        default=None,
        description="Caller-only UTC time of successful check-in, or null. No participant coordinates are returned.",
    )
    completed_at: datetime | None = Field(
        default=None,
        description="Caller-only UTC finalization time for COMPLETED, otherwise null.",
    )
    no_show_at: datetime | None = Field(
        default=None,
        description="Caller-only UTC finalization time for NO_SHOW, otherwise null.",
    )


class ActivityRead(ActivityListItem):
    cancelled_at: datetime | None = Field(
        default=None,
        description="UTC time of organizer cancellation, or null. Cancellation preserves memberships.",
    )
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
        description="Public normal UTC opening: start_at minus ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE (default 60), inclusive.",
    )
    confirmation_deadline_at: datetime | None = Field(
        default=None,
        description="Public normal UTC deadline: start_at minus ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE (default 30), exclusive. Never varies by caller. Late joins/promotions use the effective deadline in current_user_participation.",
    )
    checkin_opens_at: datetime | None = Field(
        default=None,
        description="Derived inclusive UTC opening: start_at minus configured minutes (default 30).",
    )
    checkin_closes_at: datetime | None = Field(
        default=None,
        description="Derived exclusive UTC deadline: earlier of start_at plus configured minutes (default 60) and end_at.",
    )
    checkin_radius_m: int | None = Field(
        default=None,
        description="Public configured proximity radius in meters (default 150), enforced by PostGIS ST_DWithin.",
    )
    price_amount: float | None = Field(
        description="Price in PLN for PAID activities, otherwise null."
    )
    currency: str | None = Field(
        description="Currency code for paid activities (`PLN`), otherwise null."
    )
    current_user_participation: ActivityParticipationRead | None = Field(
        default=None,
        description=(
            "The authenticated caller's current, waitlisted, or final attendance, or null for anonymous "
            "users, organizers, non-members, and inactive LEFT records. Never another user's membership."
        ),
    )
    permissions: ActivityPermissionsRead = Field(
        default_factory=ActivityPermissionsRead,
        description=(
            "Caller-specific activity, participation and private gallery permissions. Final outcomes block attendance mutations; COMPLETED may still use the gallery until end_at + 72h. Check-in still requires location validation."
        ),
    )


# Complete valid response examples; all participation mutations return ActivityRead.
ACTIVITY_JOIN_RESPONSE_EXAMPLE = ActivityRead.model_validate(
    {
        "id": "d54112d9-43cf-4986-8679-b6c236ac522c",
        "title": ACTIVITY_CREATE_EXAMPLE["title"],
        "description": ACTIVITY_CREATE_EXAMPLE["description"],
        "category": {
            "id": ActivityCategoryId.TEAM_SPORT.value,
            "name": ACTIVITY_CATEGORIES[ActivityCategoryId.TEAM_SPORT].name,
            "slug": ACTIVITY_CATEGORIES[ActivityCategoryId.TEAM_SPORT].slug,
        },
        "start_at": ACTIVITY_CREATE_EXAMPLE["start_at"],
        "end_at": ACTIVITY_CREATE_EXAMPLE["end_at"],
        "location_name": ACTIVITY_CREATE_EXAMPLE["location_name"],
        "address": ACTIVITY_CREATE_EXAMPLE["address"],
        "latitude": 52.4232,
        "longitude": 16.9461,
        "price_type": "FREE",
        "price_amount": None,
        "currency": None,
        "min_participants": 4,
        "max_participants": 12,
        "participant_count": 1,
        "checked_in_count": 0,
        "waitlist_count": 0,
        "available_slots": 11,
        "status": "PUBLISHED",
        "organizer": {
            "id": "bb1aedb3-54f4-45c4-ab10-2fb0a07b53ca",
            "display_name": "Organizer",
            "avatar_url": None,
        },
        "current_user_participation": {
            "status": "JOINED",
            "joined_at": "2030-08-01T12:00:00Z",
            "effective_confirmation_deadline_at": "2030-08-08T15:30:00Z",
        },
        "confirmation_opens_at": "2030-08-08T15:00:00Z",
        "confirmation_deadline_at": "2030-08-08T15:30:00Z",
        "checkin_opens_at": "2030-08-08T15:30:00Z",
        "checkin_closes_at": "2030-08-08T17:00:00Z",
        "checkin_radius_m": 150,
        "permissions": {"can_leave": True},
    }
).model_dump(mode="json")
ACTIVITY_LEAVE_RESPONSE_EXAMPLE = {
    **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    "participant_count": 0,
    "available_slots": 12,
    "current_user_participation": None,
    "permissions": ActivityPermissionsRead(can_join=True).model_dump(),
}
ACTIVITY_WAITLIST_RESPONSE_EXAMPLE = ActivityRead.model_validate(
    {
        **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
        "participant_count": 12,
        "available_slots": 0,
        "waitlist_count": 3,
        "current_user_participation": {
            "status": "WAITLISTED",
            "joined_at": None,
            "waitlisted_at": "2030-08-01T12:05:00Z",
            "waitlist_position": 3,
        },
        "permissions": ActivityPermissionsRead(can_leave=True).model_dump(),
    }
).model_dump(mode="json")
ACTIVITY_PROMOTED_RESPONSE_EXAMPLE = ActivityRead.model_validate(
    {
        **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
        "participant_count": 12,
        "available_slots": 0,
        "waitlist_count": 2,
        "current_user_participation": {
            "status": "JOINED",
            "joined_at": "2030-08-08T15:30:00Z",
            "effective_confirmation_deadline_at": "2030-08-08T15:40:00Z",
            "waitlisted_at": "2030-08-01T12:00:00Z",
            "waitlist_position": None,
        },
        "permissions": ActivityPermissionsRead(
            can_leave=True, can_confirm=True
        ).model_dump(),
    }
).model_dump(mode="json")
ACTIVITY_CONFIRM_RESPONSE_EXAMPLE = {
    **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    "current_user_participation": {
        "status": "CONFIRMED",
        "joined_at": "2030-08-01T12:00:00Z",
        "waitlisted_at": None,
        "waitlist_position": None,
        "confirmed_at": "2030-08-08T15:05:00Z",
        "effective_confirmation_deadline_at": None,
        "confirmation_expired_at": None,
        "waitlist_expired_at": None,
        "checked_in_at": None,
        "completed_at": None,
        "no_show_at": None,
    },
    "permissions": ActivityPermissionsRead(can_leave=True).model_dump(),
}
ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE = {
    **ACTIVITY_CONFIRM_RESPONSE_EXAMPLE,
    "checked_in_count": 1,
    "current_user_participation": {
        **ACTIVITY_CONFIRM_RESPONSE_EXAMPLE["current_user_participation"],
        "status": "CHECKED_IN",
        "checked_in_at": "2030-08-08T15:45:00Z",
    },
    "permissions": ActivityPermissionsRead(
        can_view_gallery=True, can_upload_photo=True
    ).model_dump(),
}
ACTIVITY_COMPLETED_RESPONSE_EXAMPLE = ActivityRead.model_validate(
    {
        **ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE,
        "status": "ENDED",
        "participant_count": 0,
        "available_slots": 12,
        "current_user_participation": {
            **ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE["current_user_participation"],
            "status": "COMPLETED",
            "completed_at": "2030-08-08T18:00:00Z",
        },
    }
).model_dump(mode="json")
ACTIVITY_NO_SHOW_RESPONSE_EXAMPLE = ActivityRead.model_validate(
    {
        **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
        "status": "ENDED",
        "participant_count": 0,
        "available_slots": 12,
        "current_user_participation": {
            **ACTIVITY_JOIN_RESPONSE_EXAMPLE["current_user_participation"],
            "status": "NO_SHOW",
            "effective_confirmation_deadline_at": None,
            "no_show_at": "2030-08-08T18:00:00Z",
        },
        "permissions": ActivityPermissionsRead().model_dump(),
    }
).model_dump(mode="json")
ACTIVITY_FINALIZE_RESPONSE_EXAMPLE = {
    **ACTIVITY_COMPLETED_RESPONSE_EXAMPLE,
    "current_user_participation": None,
    "permissions": ActivityPermissionsRead(can_view_gallery=True).model_dump(),
}
ACTIVITY_CONFIRMATION_EXPIRED_RESPONSE_EXAMPLE = ActivityRead.model_validate(
    {
        **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
        "participant_count": 0,
        "available_slots": 12,
        "current_user_participation": {
            **ACTIVITY_JOIN_RESPONSE_EXAMPLE["current_user_participation"],
            "status": "CONFIRMATION_EXPIRED",
            "effective_confirmation_deadline_at": None,
            "confirmation_expired_at": "2030-08-08T15:30:00Z",
        },
        "permissions": ActivityPermissionsRead().model_dump(),
    }
).model_dump(mode="json")
ACTIVITY_WAITLIST_EXPIRED_RESPONSE_EXAMPLE = ActivityRead.model_validate(
    {
        **ACTIVITY_WAITLIST_RESPONSE_EXAMPLE,
        "status": "ONGOING",
        "waitlist_count": 0,
        "current_user_participation": {
            **ACTIVITY_WAITLIST_RESPONSE_EXAMPLE["current_user_participation"],
            "status": "WAITLIST_EXPIRED",
            "waitlist_position": None,
            "waitlist_expired_at": "2030-08-08T16:00:00Z",
        },
        "permissions": ActivityPermissionsRead().model_dump(),
    }
).model_dump(mode="json")
