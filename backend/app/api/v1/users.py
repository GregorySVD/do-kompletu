from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.activity import ActivityRead
from app.schemas.my_activities import MY_ACTIVITIES_RESPONSE_EXAMPLES, MyActivitiesQuery
from app.schemas.user import UserRead, UserUpdate
from app.services.activity_service import activity_to_read, list_user_activities
from app.services.auth_service import DuplicateUsernameError, update_user_profile

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me/activities",
    response_model=list[ActivityRead],
    summary="List the current user's activities",
    description="""
Read your organized, joined, or waitlisted activities. An **access JWT is required**: use
Swagger **Authorize** (email or display name in `username`) or send
`Authorization: Bearer <access_token>`. Refresh tokens are not accepted.
Identity always comes from the JWT; `user_id` and other unknown query fields are
rejected with 422. This endpoint never exposes another caller's membership.

## RELATION

`relation=organized` selects activities you organize, without treating you as a
participant. `relation=joined` selects JOINED/CONFIRMED/CHECKED_IN before end;
history also includes final COMPLETED/NO_SHOW outcomes. LEFT records and organizer
activities are excluded. `relation=waitlisted` selects only your WAITLISTED rows,
separately from joined. Relation is required; there is no combined/all relation.

## TIME AND SORTING

One UTC cutoff is captured per request for filters, status, and permissions.
`scope=upcoming` means `end_at > cutoff`, including ongoing activities, ordered
by `start_at ASC, id ASC`. `scope=history` means `end_at <= cutoff`, ordered by
`end_at DESC, id ASC` (most recently ended first).

Omit scope for all times: upcoming/ongoing first by start time, then history by
descending end time; UUID ascending breaks ties in both groups. The exact end
instant belongs to history. There is no separate ongoing filter.

## FRONTEND SECTIONS AND PAGINATION

Use `?relation=joined&scope=upcoming` for Nadchodzące,
`?relation=waitlisted&scope=upcoming` for the Waitlist section,
`?relation=organized` for Organizowane przeze mnie (all times), and
`?relation=joined&scope=history` for Historia.

The response is a JSON **array**, reusing ActivityRead. `limit` defaults to 20
(1-100); `offset` defaults to 0 (nonnegative). Filters and sorting precede pagination.
An empty page returns `[]`. There is no total count, has_more, or wrapper. Fetch
the next offset until a short/empty page; a full final page may need one empty fetch.
Separate requests use fresh cutoffs/snapshots, so time or membership changes can
shift offsets; pagination does not freeze the dataset.

## STATE AND LIMITATIONS

Waitlisted items include private waitlisted_at and 1-based waitlist_position
(waitlisted_at ASC, user_id ASC), with joined_at=null. Promotion changes the row
to JOINED, sets joined_at and preserves waitlisted_at; position becomes null.
Waitlisted uses the same end-time scope as other relations. The periodic worker
expires overdue JOINED reservations and remaining WAITLISTED at start. Expired
states are excluded from joined/waitlisted relations but remain private on direct
detail with expiry timestamps. Cancellation skips automation and preserves its
existing evidence, so cancelled waitlists can remain in their original relation.
State changes are visible after refetch; no WebSocket/push channel is implemented.
Joined items include your own current or final state, joined_at, and nullable
confirmed_at/checked_in_at/completed_at/no_show_at, plus effective_confirmation_deadline_at
for JOINED. LEFT and system-expired states are inactive and excluded.
Organized items normally have null membership. Counts/capacity use only unresolved
JOINED/CONFIRMED/CHECKED_IN states; organizers do not consume places, and unlimited
activities have available_slots=null. Finalization reduces participant_count to
zero, while checked_in_count preserves CHECKED_IN + COMPLETED.
Cancelled activities remain in all relations and retain the same end-time scope;
their status remains CANCELLED. can_edit/can_cancel follow organizer lifecycle rules;
ended/cancelled/checked-in/final memberships cannot leave. Organizer can_finalize
is true only for uncancelled ended activities with unresolved attendance. Explicit
organizer finalization maps CHECKED_IN to COMPLETED and JOINED/CONFIRMED to NO_SHOW;
cancelled activities cannot be finalized. waitlist_count counts WAITLISTED only,
which never consumes capacity and cannot confirm/check in. can_join permits a
JOINED or WAITLISTED result strictly before start, even when full. Confirmation and
PostGIS check-in use their published windows. Finalization awards +10 points only
for new CHECKED_IN -> COMPLETED transitions; read your balance via /users/me.
Activity deletion is not implemented. Responses are private and must not
be cached by shared intermediaries. Scope client query caches to the current user.
""",
    response_description="A page of your activity details with your own state and permissions.",
    responses={
        200: {
            "content": {
                "application/json": {"examples": MY_ACTIVITIES_RESPONSE_EXAMPLES}
            }
        },
        401: {
            "description": "An active user and valid access token are required.",
            "content": {
                "application/json": {
                    "examples": {
                        "missing": {"value": {"detail": "Not authenticated"}},
                        "invalid": {
                            "value": {"detail": "Could not validate credentials"}
                        },
                    }
                }
            },
        },
        422: {
            "description": "Missing/invalid relation, invalid scope, pagination, or unknown query field.",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "type": "greater_than_equal",
                                "loc": ["query", "limit"],
                                "msg": "Input should be greater than or equal to 1",
                                "input": "0",
                                "ctx": {"ge": 1},
                            }
                        ]
                    }
                }
            },
        },
    },
)
def read_current_user_activities(
    filters: Annotated[MyActivitiesQuery, Query()],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    response: Response,
) -> list[ActivityRead]:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    results = list_user_activities(
        session,
        current_user_id=current_user.id,
        relation=filters.relation,
        scope=filters.scope,
        limit=filters.limit,
        offset=filters.offset,
    )
    return [activity_to_read(result) for result in results]


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the current user",
    description="Return the caller's own profile and account state, including is_active and is_admin, using the access bearer token.",
    response_description="The authenticated user's own profile and account state.",
    responses={
        401: {
            "description": "The access token is missing, invalid, or expired.",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not validate credentials"}
                }
            },
        }
    },
)
def read_current_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update the current user's profile",
    description=(
        "Update the authenticated user's display name and/or avatar. Display names "
        "remain unique case-insensitively."
    ),
    response_description="The updated public user profile.",
    responses={
        401: {"description": "A valid access bearer token is required."},
        409: {
            "description": "The requested display name is already used.",
            "content": {
                "application/json": {"example": {"detail": "Username is already taken"}}
            },
        },
        422: {"description": "The profile update payload is invalid."},
    },
)
def patch_current_user(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> UserRead:
    try:
        updated_user = update_user_profile(session, current_user, payload)
    except DuplicateUsernameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken",
        ) from exc
    return UserRead.model_validate(updated_user)
