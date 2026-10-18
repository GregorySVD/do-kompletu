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
Read your organized or joined activities. An **access JWT is required**: use
Swagger **Authorize** (email or display name in `username`) or send
`Authorization: Bearer <access_token>`. Refresh tokens are not accepted.
Identity always comes from the JWT; `user_id` and other unknown query fields are
rejected with 422. This endpoint never exposes another caller's membership.

## RELATION

`relation=organized` selects activities you organize, without treating you as a
participant. `relation=joined` selects your persisted memberships, excluding
organizer activities. Relation is required; there is no combined/all relation.

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
`?relation=organized` for Organizowane przeze mnie (all times), and
`?relation=joined&scope=history` for Historia.

The response is a JSON **array**, reusing ActivityRead. `limit` defaults to 20
(1-100); `offset` defaults to 0 (nonnegative). Filters and sorting precede pagination.
An empty page returns `[]`. There is no total count, has_more, or wrapper. Fetch
the next offset until a short/empty page; a full final page may need one empty fetch.
Separate requests use fresh cutoffs/snapshots, so time or membership changes can
shift offsets; pagination does not freeze the dataset.

## STATE AND LIMITATIONS

Joined items include your `JOINED` state and joined_at; organized items normally
have null membership. Counts/capacity come from persisted memberships; organizers
do not consume places, and unlimited activities have available_slots=null.
can_join/can_leave follow existing lifecycle rules; ended memberships cannot leave.
Checked-in/waitlist counts stay zero; editing, cancellation, deletion, and future
attendance/reward actions are not implemented. Responses are private and must not
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
    description="Return the public profile associated with the access bearer token.",
    response_description="The authenticated user's public profile.",
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
