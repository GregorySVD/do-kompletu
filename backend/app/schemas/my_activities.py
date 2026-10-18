from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.activity import (
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
            "organized: you are the organizer; joined: you have persisted membership. "
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
                "current_user_participation": {
                    "status": "JOINED",
                    "joined_at": "2025-08-01T12:00:00Z",
                },
                "permissions": ActivityPermissionsRead().model_dump(),
            }
        ],
    },
    "empty": {"summary": "No matches, or offset beyond the last item", "value": []},
}
