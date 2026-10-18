from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.activity import (
    ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE,
    ACTIVITY_CONFIRM_RESPONSE_EXAMPLE,
    ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    ActivityPermissionsRead,
)


class ActivityRelation(StrEnum):
    ORGANIZED = "organized"
    JOINED = "joined"


class ActivityScope(StrEnum):
    UPCOMING = "upcoming"
    HISTORY = "history"


class MyActivitiesQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relation: ActivityRelation = Field(
        description=(
            "organized: you are the organizer; joined: you have active JOINED/CONFIRMED/CHECKED_IN membership (LEFT excluded). "
            "Organizer identity alone never counts as joined membership."
        ),
    )
    scope: ActivityScope | None = Field(
        default=None,
        description=(
            "upcoming: end_at > the request's UTC cutoff (includes ongoing); "
            "history: end_at <= cutoff. Omit for all times, including the current "
            "frontend's all-organized section."
        ),
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum items (1-100).")
    offset: int = Field(
        default=0, ge=0, description="Matching items to skip (0 or more)."
    )


MY_ACTIVITIES_RESPONSE_EXAMPLES = {
    "checked_in_upcoming": {
        "summary": "Checked-in caller with private checked_in_at and public checked_in_count",
        "value": [ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE],
    },
    "confirmed_upcoming": {
        "summary": "Active confirmed membership with caller-only confirmed_at",
        "value": [ACTIVITY_CONFIRM_RESPONSE_EXAMPLE],
    },
    "joined_upcoming": {
        "summary": "Joined upcoming activity with one participant",
        "value": [ACTIVITY_JOIN_RESPONSE_EXAMPLE],
    },
    "organized": {
        "summary": "Your organized activity; organizer is separate from membership",
        "value": [
            {
                **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
                "current_user_participation": None,
                "permissions": ActivityPermissionsRead(
                    can_edit=True, can_cancel=True
                ).model_dump(),
            }
        ],
    },
    "joined_history": {
        "summary": "Ended membership preserved in your history",
        "value": [
            {
                **ACTIVITY_JOIN_RESPONSE_EXAMPLE,
                "start_at": "2025-08-08T16:00:00Z",
                "end_at": "2025-08-08T18:00:00Z",
                "status": "ENDED",
                "confirmation_opens_at": "2025-08-07T16:00:00Z",
                "confirmation_deadline_at": "2025-08-08T16:00:00Z",
                "checkin_opens_at": "2025-08-08T15:30:00Z",
                "checkin_closes_at": "2025-08-08T17:00:00Z",
                "current_user_participation": {
                    "status": "JOINED",
                    "joined_at": "2025-08-01T12:00:00Z",
                    "confirmed_at": None,
                    "checked_in_at": None,
                },
                "permissions": ActivityPermissionsRead().model_dump(),
            }
        ],
    },
    "empty": {"summary": "No matches, or offset beyond the last item", "value": []},
}
