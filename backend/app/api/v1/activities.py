from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Path,
    Query,
    Response,
    status,
)
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_optional_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.activity import (
    ACTIVITY_CATEGORY_MARKDOWN_TABLE,
    ACTIVITY_CREATE_EXAMPLES,
    ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    ACTIVITY_LEAVE_RESPONSE_EXAMPLE,
    ActivityCategoryId,
    ActivityCreate,
    ActivityListItem,
    ActivityRead,
    PriceType,
)
from app.schemas.activity_management import (
    ACTIVITY_CANCEL_RESPONSE_EXAMPLE,
    ACTIVITY_PATCH_EXAMPLES,
    ACTIVITY_PATCH_RESPONSE_EXAMPLE,
    ActivityUpdate,
)
from app.services.activity_management_service import (
    ActivityManagementError,
    cancel_activity,
    update_activity,
)
from app.services.activity_service import (
    activity_to_list_item,
    activity_to_read,
    create_activity,
    get_activity_by_id,
    list_activities,
)
from app.services.participation_service import (
    ParticipationError,
    join_activity,
    leave_activity,
)

router = APIRouter(prefix="/activities", tags=["Activities"])

ACTIVITY_CREATE_DESCRIPTION = f"""
Create and persist a new activity.

## AUTHENTICATION

Send an access token as `Authorization: Bearer <token>`. Refresh tokens are not
accepted. The authenticated user becomes the organizer.

## CATEGORIES

`category_id` must be one of the canonical IDs below. The same reference data is
available from `GET /api/v1/categories`.

{ACTIVITY_CATEGORY_MARKDOWN_TABLE}

## TIME

`start_at` and `end_at` must include a timezone offset. The API normalizes them to
UTC and requires `end_at` to be later than `start_at`. Example:
`2030-08-08T16:00:00Z`.

## LOCATION

Provide a display name, address, WGS 84 latitude from -90 to 90, and longitude from
-180 to 180. Coordinates are stored as PostGIS `Geography(Point, 4326)`.

## PARTICIPANTS

`min_participants` must be from 2 to 100. When `has_participant_limit` is `true`,
`max_participants` is required, must be from 2 to 100, and cannot be below the
minimum. When it is `false`, `max_participants` must be `null`.

## PRICE

Use `FREE` with a null `price_amount`, for example
`{{"price_type": "FREE", "price_amount": null}}`. Use `PAID` with a positive PLN
amount of at most two decimal places, for example
`{{"price_type": "PAID", "price_amount": 40.00}}`.

## ORGANIZER

The organizer is derived exclusively from the bearer token. Clients cannot provide
or override an `organizer_id`, so they cannot create an activity in another user's
name.

## CURRENT LIMITATIONS

Create, list, detail, edit, cancel, join, and leave are implemented. The organizer is separate
from membership and does not consume a participant place. Counts reflect persisted
memberships. Waitlists, confirmations, check-in, galleries, and nearby-distance
calculation are not implemented; their related fields remain placeholders.
"""


@router.post(
    "",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an activity",
    description=ACTIVITY_CREATE_DESCRIPTION,
    response_description="The created activity including its authenticated organizer.",
    responses={
        401: {
            "description": "A valid access bearer token is required.",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not validate credentials"}
                }
            },
        },
        422: {
            "description": (
                "Payload validation failed, including time, participant, price, "
                "category, or coordinate rules."
            )
        },
    },
)
def create(
    payload: Annotated[
        ActivityCreate,
        Body(openapi_examples=ACTIVITY_CREATE_EXAMPLES),
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ActivityRead:
    result = create_activity(session, payload, current_user)
    return activity_to_read(result)


def _management_responses(*conflicts: str) -> dict:
    return {
        401: {"description": "A valid access JWT for an active user is required."},
        403: {
            "description": "The authenticated caller is not the organizer.",
            "content": {
                "application/json": {
                    "example": {"detail": "Only the organizer can manage this activity"}
                }
            },
        },
        404: {
            "description": "The activity does not exist.",
            "content": {
                "application/json": {"example": {"detail": "Activity not found"}}
            },
        },
        409: {
            "description": "Lifecycle or current membership prevents this operation.",
            "content": {
                "application/json": {
                    "examples": {
                        f"conflict_{index}": {
                            "summary": detail,
                            "value": {"detail": detail},
                        }
                        for index, detail in enumerate(conflicts)
                    }
                }
            },
        },
        422: {
            "description": "Invalid UUID or payload, including validation of the merged activity state."
        },
    }


@router.patch(
    "/{activity_id}",
    response_model=ActivityRead,
    summary="Edit an activity as its organizer",
    description="""
Use an access JWT through **Authorize** or `Authorization: Bearer <access_token>`.
Only the organizer can edit. Editing is allowed strictly before the existing
start_at, unless cancelled. Ongoing/ended activities return 409. A proposed start
must also remain strictly in the future (422 otherwise).

This is a true partial update: omitted fields stay unchanged. Empty objects,
unknown fields, organizer_id, status, cancelled_at, and internal counters are
rejected with 422. Only max_participants and price_amount accept explicit null.
Editable fields are title, description, category_id, start_at, end_at,
location_name, address, latitude, longitude, min_participants,
has_participant_limit, max_participants, price_type, and price_amount.

The merged result is validated using the creation contract: trimmed text and
length limits, canonical category UUID, timezone-aware UTC-normalized times with
end_at > start_at, WGS 84 coordinate ranges, participant minimum/maximum (2-100),
and price consistency. One coordinate can change while the other stays unchanged.

Set has_participant_limit=true together with a valid maximum when enabling a
limit. Set has_participant_limit=false and max_participants=null to remove it.
Finite capacity must be at least min_participants and the current membership
count; a limit below membership returns 409. Set PAID together with a positive
PLN price_amount (at most two decimal places); switching to FREE requires explicit
price_amount=null. Omission does not silently clear a price or maximum.

The activity-row lock is shared with join, leave, and cancellation. Counts are
checked after the lock and held through the update and response snapshot. The
200 response is your updated ActivityRead, with organizer permissions and real
capacity. No participant rows are removed or notifications sent.
""",
    response_description="Updated activity details with the organizer's own permissions.",
    responses={
        200: {
            "content": {
                "application/json": {"example": ACTIVITY_PATCH_RESPONSE_EXAMPLE}
            }
        },
        **_management_responses(
            "Activity is cancelled",
            "Activity can only be edited before it starts",
            "Participant limit cannot be below current participant count",
        ),
    },
)
def patch(
    activity_id: Annotated[
        UUID, Path(description="Activity UUID owned by the current user.")
    ],
    payload: Annotated[ActivityUpdate, Body(openapi_examples=ACTIVITY_PATCH_EXAMPLES)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ActivityRead:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return activity_to_read(
            update_activity(session, activity_id, current_user.id, payload)
        )
    except ActivityManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValidationError as exc:
        raise RequestValidationError(
            [
                {**error, "loc": ("body", *error["loc"])}
                for error in exc.errors(include_url=False)
            ]
        ) from exc


@router.post(
    "/{activity_id}/cancel",
    response_model=ActivityRead,
    summary="Cancel an activity as its organizer",
    description="""
An access JWT is required; use **Authorize** or Authorization: Bearer <access_token>.
Only the organizer can cancel. No request body is needed. Cancellation is allowed
strictly before end_at, including while ONGOING. Ended or already cancelled
activities return 409; another user receives 403.

Cancellation sets cancelled_at to the current UTC time under the same activity-row
lock as edit/join/leave. It preserves the activity and every membership; status is
CANCELLED permanently, taking priority over the timestamp-derived lifecycle.

Cancelled activities are excluded from public GET /activities discovery, but their
direct detail remains available. Organized and joined My Activities lists retain
them: end_at > cutoff is upcoming, end_at <= cutoff is history, even when status
is CANCELLED. Counts and available slots continue to describe persisted membership.
They do not mean cancelled places are bookable.

New joins and leaving are blocked with 409 after cancellation, preserving membership
history. All cancelled activity permissions are false, including can_edit,
can_cancel, can_join, and can_leave. There is no hard deletion, uncancel, cancellation
reason, notification, refund, or payment processing in this milestone.
""",
    response_description="Cancelled activity details; the activity and memberships are preserved.",
    responses={
        200: {
            "content": {
                "application/json": {"example": ACTIVITY_CANCEL_RESPONSE_EXAMPLE}
            }
        },
        **_management_responses("Activity is cancelled", "Activity has ended"),
    },
)
def cancel(
    activity_id: Annotated[
        UUID, Path(description="Activity UUID owned by the current user.")
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ActivityRead:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return activity_to_read(cancel_activity(session, activity_id, current_user.id))
    except ActivityManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "",
    response_model=list[ActivityListItem],
    summary="List activities",
    description=(
        "Return public activity cards/map items, excluding cancelled activities. Results are stable: active and "
        "upcoming activities first, then start time and UUID. `distance_m` remains "
        "null until nearby search is implemented."
    ),
    response_description="A paginated array of activity list/map projections.",
    responses={422: {"description": "A filter or pagination parameter is invalid."}},
)
def list_all(
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[
        int,
        Query(ge=1, le=100, description="Maximum number of records to return."),
    ] = 20,
    offset: Annotated[
        int,
        Query(ge=0, description="Number of matching records to skip."),
    ] = 0,
    query: Annotated[
        str | None,
        Query(
            max_length=100,
            description="Case-insensitive text search over title, place, and address.",
        ),
    ] = None,
    category_id: Annotated[
        ActivityCategoryId | None,
        Query(description="Exact canonical category ID."),
    ] = None,
    price_type: Annotated[
        PriceType | None,
        Query(description="Filter to FREE or PAID activities."),
    ] = None,
) -> list[ActivityListItem]:
    results = list_activities(
        session,
        limit=limit,
        offset=offset,
        query=query,
        category_id=category_id,
        price_type=price_type,
    )
    return [activity_to_list_item(result) for result in results]


@router.get(
    "/{activity_id}",
    response_model=ActivityRead,
    summary="Get activity details",
    # FastAPI merges this anonymous alternative with the generated bearer scheme.
    openapi_extra={"security": [{}]},
    description=(
        "Return public details and the organizer's safe public identity. Password "
        "hashes and other internal user fields are never exposed. Authentication "
        "is optional: omit Authorization for anonymous browsing, or send an access "
        "bearer token for your own membership and join/leave permissions. Supplied "
        "invalid/expired credentials return 401. Membership counts are public; "
        "other users' memberships are never returned. Cancelled activities remain "
        "readable here, including status and cancelled_at. Responses must not be cached."
    ),
    response_description="The requested activity details.",
    responses={
        401: {"description": "Supplied bearer credentials are invalid or expired."},
        404: {
            "description": "No activity exists for the supplied UUID.",
            "content": {
                "application/json": {"example": {"detail": "Activity not found"}}
            },
        },
        422: {"description": "The path parameter is not a valid UUID."},
    },
)
def read(
    activity_id: Annotated[UUID, Path(description="Activity UUID.")],
    session: Annotated[Session, Depends(get_db)],
    current_user: Annotated[User | None, Depends(get_optional_current_user)],
    response: Response,
) -> ActivityRead:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"
    result = get_activity_by_id(
        session,
        activity_id,
        current_user_id=current_user.id if current_user is not None else None,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )
    return activity_to_read(result)


def _membership_responses(*conflicts: str) -> dict:
    return {
        401: {
            "description": "Authentication required: use an access JWT, not a refresh JWT.",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not validate credentials"}
                }
            },
        },
        404: {
            "description": "No activity exists for this UUID.",
            "content": {
                "application/json": {"example": {"detail": "Activity not found"}}
            },
        },
        409: {
            "description": "Membership change conflicts with current activity state.",
            "content": {
                "application/json": {
                    "examples": {
                        f"conflict_{index}": {
                            "summary": detail,
                            "value": {"detail": detail},
                        }
                        for index, detail in enumerate(conflicts)
                    }
                }
            },
        },
        422: {"description": "The activity_id path parameter is not a valid UUID."},
    }


@router.post(
    "/{activity_id}/join",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
    summary="Join an activity",
    description="""
Create active membership for the authenticated caller. No request body is needed.

In Swagger, register/login as a user other than the organizer, select **Authorize**
(email or display name in `username`), and paste a real activity UUID into
`activity_id`. Public `GET /api/v1/activities` supplies activity IDs.

Send `Authorization: Bearer <access_token>`; refresh tokens are not accepted.
The organizer cannot join and is excluded from participant counts and capacity.
Joining is allowed before and during the activity, strictly before `end_at`.
Cancelled activities reject joining with 409.
Duplicate joins return 409, including when the activity is full. Full activities
return 409; `max_participants: null` means unlimited places.

PostgreSQL serializes join/leave transactions using a lock on the activity row.
The 201 response contains updated activity details, counts, your `JOINED` state,
and permissions. `JOINED` does not mean confirmed attendance or check-in.
Waitlist and check-in counts remain zero. Retry after an uncertain network result
by reading details; another POST after a successful join returns 409.
""",
    response_description="Updated activity details including your new active membership.",
    responses={
        201: {
            "content": {"application/json": {"example": ACTIVITY_JOIN_RESPONSE_EXAMPLE}}
        },
        **_membership_responses(
            "Already joined this activity",
            "Activity is full",
            "Activity has ended",
            "Activity is cancelled",
            "Organizer cannot join or leave their own activity",
        ),
    },
)
def join(
    activity_id: Annotated[UUID, Path(description="UUID from an existing activity.")],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ActivityRead:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return activity_to_read(join_activity(session, activity_id, current_user.id))
    except ParticipationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.delete(
    "/{activity_id}/join",
    response_model=ActivityRead,
    summary="Leave an activity",
    description="""
Remove the authenticated caller's active membership. No request body is needed.
Send an access JWT using **Authorize** or `Authorization: Bearer <access_token>`.
First join as a non-organizer with POST on this same path, then try DELETE.

The 200 response is the updated activity detail: participant count decreases,
capacity becomes available, and `current_user_participation` becomes null.
The organizer cannot leave because organizers are separate from membership.
Leaving is allowed before and during an activity, strictly before `end_at`.
Ended membership is preserved for history; leaving after the end returns 409.
Cancelled membership is also preserved; leaving after cancellation returns 409.

A user without membership receives 409 (including a repeated DELETE); the stored
state is unchanged. Membership may be created again by joining while eligible.
Join and leave use the same PostgreSQL activity-row lock, preventing counter races.
""",
    response_description="Updated activity details after removing your membership.",
    responses={
        200: {
            "content": {
                "application/json": {"example": ACTIVITY_LEAVE_RESPONSE_EXAMPLE}
            }
        },
        **_membership_responses(
            "Not participating in this activity",
            "Activity has ended",
            "Activity is cancelled",
            "Organizer cannot join or leave their own activity",
        ),
    },
)
def leave(
    activity_id: Annotated[UUID, Path(description="UUID of the joined activity.")],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ActivityRead:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return activity_to_read(leave_activity(session, activity_id, current_user.id))
    except ParticipationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
