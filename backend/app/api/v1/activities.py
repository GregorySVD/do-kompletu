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
    ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE,
    ACTIVITY_CONFIRM_RESPONSE_EXAMPLE,
    ACTIVITY_CONFIRMATION_EXPIRED_RESPONSE_EXAMPLE,
    ACTIVITY_CREATE_EXAMPLES,
    ACTIVITY_FINALIZE_RESPONSE_EXAMPLE,
    ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    ACTIVITY_LEAVE_RESPONSE_EXAMPLE,
    ACTIVITY_PROMOTED_RESPONSE_EXAMPLE,
    ACTIVITY_WAITLIST_EXPIRED_RESPONSE_EXAMPLE,
    ACTIVITY_WAITLIST_RESPONSE_EXAMPLE,
    ActivityCategoryId,
    ActivityCreate,
    ActivityListItem,
    ActivityRead,
    PriceType,
)
from app.schemas.activity_check_in import (
    ACTIVITY_CHECK_IN_REQUEST_EXAMPLE,
    ActivityCheckIn,
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
    finalize_activity,
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
    check_in_activity,
    confirm_activity,
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

Create, list, detail, edit, cancel, join, leave, attendance confirmation, and PostGIS check-in are implemented. The organizer is separate
from membership and does not consume a participant place. Counts reflect persisted
JOINED/CONFIRMED/CHECKED_IN memberships; LEFT records do not count. Waitlists, galleries, and nearby-distance
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
count (JOINED/CONFIRMED/CHECKED_IN only); a limit below membership returns 409.
WAITLISTED consumes no place. Capacity edits fill newly free places FIFO before
start, including promotion of every waiter when switching to unlimited. Promotion
is one bulk UPDATE inside this same activity-locked transaction, never post-commit.
Set PAID together with a positive
PLN price_amount (at most two decimal places); switching to FREE requires explicit
price_amount=null. Omission does not silently clear a price or maximum.
Only active states consume capacity. Changing start_at or end_at while any
participant is CONFIRMED or CHECKED_IN returns 409. Once anyone is CHECKED_IN,
actual latitude/longitude/location_name/address changes also return 409. Unchanged
values and other allowed edits remain valid. LEFT records do not block edits.

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
            "Cannot change schedule while participants are confirmed",
            "Cannot change location after participants have checked in",
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
can_cancel, can_join, can_leave, and can_confirm. Confirmation is also blocked.
WAITLISTED, JOINED, CONFIRMED, CHECKED_IN, and LEFT retain their statuses/timestamps. Only active
states count; CHECKED_IN and checked_in_at survive cancellation. Check-in is blocked
after cancellation too. There is no hard deletion, uncancel, cancellation
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


@router.post(
    "/{activity_id}/finalize",
    response_model=ActivityRead,
    summary="Finalize attendance after an activity ends",
    description="""
Use **Authorize** or Authorization: Bearer <access_token>. No request body is needed.
Only the organizer may finalize, at current UTC time >= end_at. Cancelled activities
return 409 and retain their evidence. Activity status stays ENDED, never COMPLETED.

Under the same activity-first FOR UPDATE lock as every other writer, one atomic
bulk UPDATE maps CHECKED_IN -> COMPLETED and JOINED/CONFIRMED -> NO_SHOW. System-expired
states, WAITLISTED, LEFT and
existing final outcomes remain unchanged. completed_at/no_show_at record one UTC
finalization time, preserving joined_at/confirmed_at/checked_in_at. Final outcomes
are terminal. There is no automatic scheduler, manual attendance override, undo,
XP, reward, or review implementation.

Returns the normal ActivityRead for the organizer. participant_count remains the
active capacity count and becomes zero once all unresolved rows are finalized;
checked_in_count includes CHECKED_IN + COMPLETED, preserving successful check-ins.
There is no public no-show analytics field or new wrapper. The organizer's own
current_user_participation is normally null; can_finalize becomes false.

A repeated request, or an ended activity containing only WAITLISTED/LEFT/no rows/final outcomes,
returns 409 No unresolved attendance to finalize, without changing timestamps.
Thus repeated calls are idempotent at the data level. Joined My Activities history
retains the caller's COMPLETED/NO_SHOW state/timestamps; future final states are
excluded from upcoming results. Direct detail exposes only the caller's outcome.
""",
    responses={
        200: {
            "content": {
                "application/json": {"example": ACTIVITY_FINALIZE_RESPONSE_EXAMPLE}
            }
        },
        **_management_responses(
            "Activity is cancelled",
            "Activity can only be finalized after it ends",
            "No unresolved attendance to finalize",
        ),
    },
)
def finalize(
    activity_id: Annotated[
        UUID, Path(description="Activity UUID owned by the caller.")
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ActivityRead:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return activity_to_read(
            finalize_activity(session, activity_id, current_user.id)
        )
    except ActivityManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "",
    response_model=list[ActivityListItem],
    summary="List activities",
    description=(
        "Return public activity cards/map items, excluding CANCELLED and ENDED activities. "
        "PUBLISHED and ONGOING activities are included only when cancelled_at is null "
        "and end_at is strictly later than one UTC cutoff captured for the request. "
        "Filtering precedes pagination. Results remain stable by start time and UUID. `distance_m` remains "
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
        "bearer token for your own current/final attendance and action permissions. "
        "COMPLETED/NO_SHOW include caller-only completed_at/no_show_at, never another user's state. Supplied "
        "invalid/expired credentials return 401. Membership counts are public; "
        "other users' memberships are never returned. Cancelled activities remain "
        "readable here, including status and cancelled_at. Responses must not be cached."
    ),
    response_description="The requested activity details.",
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        "joined": {"value": ACTIVITY_JOIN_RESPONSE_EXAMPLE},
                        "waitlisted": {"value": ACTIVITY_WAITLIST_RESPONSE_EXAMPLE},
                        "promoted": {"value": ACTIVITY_PROMOTED_RESPONSE_EXAMPLE},
                        "confirmation_expired": {
                            "value": ACTIVITY_CONFIRMATION_EXPIRED_RESPONSE_EXAMPLE
                        },
                        "waitlist_expired": {
                            "value": ACTIVITY_WAITLIST_EXPIRED_RESPONSE_EXAMPLE
                        },
                    }
                }
            }
        },
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
    conflicts = ("Participation has expired", *conflicts)
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
Request a place for the authenticated caller, or reuse an existing LEFT row.
Unlimited activities and limited activities with free capacity return JOINED.
A full limited activity succeeds as WAITLISTED (201), without consuming a place.
No request body is needed. Rejoin resets cycle timestamps and never inserts a
second user/activity row. Duplicate JOINED/CONFIRMED/CHECKED_IN/WAITLISTED is 409.

In Swagger, register/login as a user other than the organizer, select **Authorize**
(email or display name in `username`), and paste a real activity UUID into
`activity_id`. Public `GET /api/v1/activities` supplies activity IDs.

Send `Authorization: Bearer <access_token>`; refresh tokens are not accepted.
The organizer cannot join and is excluded from participant counts and capacity.
Joining/rejoining/entering the queue is allowed only while current UTC time is
strictly before start_at; exact start and later return 409. Cancelled and ended
activities reject joining. can_join=true allows requesting a place and may result
in JOINED or WAITLISTED; it does not guarantee immediate capacity.

PostgreSQL serializes join/leave transactions using a lock on the activity row.
The 201 response contains updated activity details, real participant_count and
waitlist_count, your JOINED or WAITLISTED state, and permissions. WAITLISTED has
joined_at=null, waitlisted_at, and a private 1-based waitlist_position, ordered by
waitlisted_at ASC then user_id ASC. WAITLISTED cannot confirm/check in; JOINED
does not mean confirmed attendance. Before start, active leave or capacity increase
promotes earliest waiters to JOINED in the same transaction, sets joined_at to
promotion time, and retains waitlisted_at. A periodic worker also expires overdue
JOINED reservations and promotes FIFO waiters atomically; remaining waiters expire
at start. Late joins/promotions receive the effective confirmation grace deadline.
Final outcomes cannot rejoin. Retry after an uncertain network result
by reading details; another POST after a successful join returns 409.
""",
    response_description="Updated activity details including your JOINED or WAITLISTED participation.",
    responses={
        201: {
            "content": {
                "application/json": {
                    "examples": {
                        "joined": {
                            "summary": "Free place: JOINED",
                            "value": ACTIVITY_JOIN_RESPONSE_EXAMPLE,
                        },
                        "waitlisted": {
                            "summary": "Full activity: FIFO WAITLISTED",
                            "value": ACTIVITY_WAITLIST_RESPONSE_EXAMPLE,
                        },
                    }
                }
            }
        },
        **_membership_responses(
            "Already joined this activity",
            "Attendance outcome is final",
            "Activity has started",
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
Transition the authenticated caller's JOINED, CONFIRMED, or WAITLISTED participation
to LEFT. The row remains stored; left_at is set, cycle timestamps are preserved.
Leaving WAITLISTED removes the caller from the queue without promoting anyone.
Before start, an active leave promotes the earliest waiter(s) into actual free
capacity in this same locked transaction. FIFO uses waitlisted_at ASC, user_id ASC.
After start, leaving remains allowed until end but never promotes a waiter.
CHECKED_IN and final COMPLETED/NO_SHOW participants cannot leave (409).
There is no undo check-in or final attendance outcome.
No request body is needed.
Send an access JWT using **Authorize** or `Authorization: Bearer <access_token>`.
First join as a non-organizer with POST on this same path, then try DELETE.

The 200 response is updated activity detail: counts reflect any promotion and
`current_user_participation` becomes null. Use authenticated detail to observe
your own promotion later; the periodic worker may change participation without
a request. No notifications or server push channel exist.
The organizer cannot leave because organizers are separate from membership.
CONFIRMED/WAITLISTED leave is allowed strictly before end_at unless cancelled.
JOINED additionally must be before its effective confirmation deadline; an overdue
reservation cannot voluntarily leave and rejoin to reset its deadline (409).
System-expired participation is terminal and cannot leave/rejoin.
Ended membership is preserved for history; leaving after the end returns 409.
Cancelled membership is also preserved; leaving after cancellation returns 409.

A user without membership receives 409 (including a repeated DELETE); the stored
state is unchanged. A LEFT user may rejoin using the same row while eligible.
Join and leave use the same PostgreSQL activity-row lock, preventing counter races.
""",
    response_description="Updated activity details after marking your retained membership LEFT.",
    responses={
        200: {
            "content": {
                "application/json": {"example": ACTIVITY_LEAVE_RESPONSE_EXAMPLE}
            }
        },
        **_membership_responses(
            "Not participating in this activity",
            "Attendance outcome is final",
            "Checked-in participants cannot leave",
            "Confirmation window has closed",
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


@router.post(
    "/{activity_id}/confirm",
    response_model=ActivityRead,
    summary="Confirm attendance as a joined participant",
    description="""
Send an access JWT using **Authorize** or Authorization: Bearer <access_token>.
No body is required. Only a non-organizer with JOINED membership may confirm.
WAITLISTED cannot confirm or check in; promotion first grants JOINED, never automatic confirmation.
Successful confirmation transitions JOINED to CONFIRMED, persists confirmed_at,
and returns the full ActivityRead with the caller's actual status. It consumes no
additional place: JOINED, CONFIRMED, and CHECKED_IN count toward capacity; LEFT does not.

ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE (default 60) and
ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE (default 30) define public normal
metadata: opening=start-60 minutes, normal deadline=start-30 minutes. The opening
is inclusive and the deadline exclusive. Configuration requires open > deadline >= 0.

Only JOINED can confirm, at opening <= now < its effective confirmation deadline.
If joined_at is before the normal deadline, its deadline is the normal deadline.
If joined_at is at/after normal deadline, its deadline is min(joined_at plus
ACTIVITY_LATE_CONFIRMATION_GRACE_MINUTES (default 10), start_at). This covers direct
late joins, eligible LEFT rejoins, and promotions. Top-level confirmation_deadline_at
always stays the public normal deadline; current_user_participation exposes the
caller's effective_confirmation_deadline_at. Exact deadline is rejected even if
an overdue database row is still JOINED because the worker has not swept yet.

A lifespan worker periodically expires overdue JOINED to CONFIRMATION_EXPIRED and
promotes FIFO waiters atomically before start. At start, remaining waiters become
WAITLIST_EXPIRED. Both states retain private evidence and cannot rejoin/confirm.
Cancelled activities are skipped; finalization remains explicit. All checks run
after the existing activity-first lock. Non-members/LEFT users, repeated confirmation,
and out-of-window attempts return 409. There is no unconfirm.

A confirmed participant may leave before end unless cancelled. Overdue JOINED cannot
leave to bypass expiry by rejoining. Leaving preserves
confirmed_at as last-cycle evidence; rejoining clears it and starts JOINED again.
Activity schedule changes are blocked while any participant remains CONFIRMED.
CHECKED_IN users cannot confirm again (409). Check-in is a separate POST with
time and PostGIS validation. After end, organizer finalization resolves attendance
to COMPLETED/NO_SHOW; these terminal outcomes cannot confirm. Rewards remain unimplemented.
""",
    responses={
        200: {
            "content": {
                "application/json": {"example": ACTIVITY_CONFIRM_RESPONSE_EXAMPLE}
            }
        },
        **_membership_responses(
            "Organizer cannot confirm their own activity",
            "Not participating in this activity",
            "Already confirmed attendance",
            "Attendance outcome is final",
            "Already checked in",
            "Activity is cancelled",
            "Activity has ended",
            "Confirmation window has not opened",
            "Confirmation window has closed",
        ),
    },
)
def confirm(
    activity_id: Annotated[UUID, Path(description="UUID of the joined activity.")],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ActivityRead:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return activity_to_read(confirm_activity(session, activity_id, current_user.id))
    except ParticipationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post(
    "/{activity_id}/check-in",
    response_model=ActivityRead,
    summary="Check in as a confirmed participant near the activity",
    description="""
Use **Authorize** or Authorization: Bearer <access_token>. Submit WGS 84 latitude
(-90..90), longitude (-180..180), and required accuracy_m, a finite positive
client-reported location accuracy radius in meters. Only a CONFIRMED non-organizer may check in;
JOINED is not implicitly confirmed, WAITLISTED has no place and is rejected with
409, LEFT is inactive, duplicate CHECKED_IN is 409.

The shared UTC check-in window is inclusive at checkin_opens_at and exclusive at
checkin_closes_at: start minus ACTIVITY_CHECK_IN_OPEN_MINUTES_BEFORE (default 30),
through the earlier of start plus ACTIVITY_CHECK_IN_CLOSE_MINUTES_AFTER (default
60) or activity end. Cancelled/ended activities cannot check in.

Under the shared activity-row lock, accuracy_m above
ACTIVITY_CHECK_IN_MAX_ACCURACY_METERS (default 100) returns 409 with
"Location accuracy is insufficient for check-in"; exactly the limit is allowed.
This helps reject naturally poor GPS fixes, but the accuracy is client-reported
and does not prove coordinates are genuine or prevent GPS spoofing.

After accuracy validation, PostgreSQL/PostGIS ST_DWithin compares the
stored Geography(Point,4326) with Point(longitude,latitude), in meters using the
spheroid. Distance <= ACTIVITY_CHECK_IN_RADIUS_METERS (default 150) is accepted;
outside returns 409. No Python/SQLite geographic fallback authorizes attendance.

Success transitions CONFIRMED to CHECKED_IN, sets checked_in_at once, preserves
joined_at/confirmed_at, and returns ActivityRead with real checked_in_count.
Submitted coordinates, accuracy_m, and distance are used transiently and are not stored or returned.
The caller's timestamps are private; public timing/radius/counts are safe metadata.
can_check_in means state/time allow an attempt; POST still validates accuracy and proximity.

CHECKED_IN remains active and consumes capacity; it cannot leave or confirm again.
Schedule/location edits are protected, and cancellation preserves check-in evidence.
Submitted coordinates can be spoofed: this is not device attestation or fraud-proof
GPS verification. After end, organizer finalization converts CHECKED_IN to COMPLETED
and unresolved JOINED/CONFIRMED to NO_SHOW; final outcomes cannot check in.
No rewards or undo check-in exists.
""",
    responses={
        200: {
            "content": {
                "application/json": {"example": ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE}
            }
        },
        **_membership_responses(
            "Organizer cannot check in to their own activity",
            "Attendance outcome is final",
            "Not participating in this activity",
            "Attendance must be confirmed before check-in",
            "Already checked in",
            "Activity is cancelled",
            "Activity has ended",
            "Check-in window has not opened",
            "Check-in window has closed",
            "Location accuracy is insufficient for check-in",
            "Outside check-in radius",
        ),
        503: {
            "description": "Check-in requires PostgreSQL/PostGIS; there is no approximate fallback."
        },
        422: {
            "description": "Invalid activity UUID or location body; latitude/longitude are required, finite, and range-checked. accuracy_m is required, finite, and greater than zero. Unknown fields are rejected."
        },
    },
)
def check_in(
    activity_id: Annotated[UUID, Path(description="UUID of the confirmed activity.")],
    payload: Annotated[
        ActivityCheckIn,
        Body(
            openapi_examples={
                "at_venue": {
                    "summary": "Coordinates at the example venue with a 20-meter accuracy radius",
                    "value": ACTIVITY_CHECK_IN_REQUEST_EXAMPLE,
                }
            }
        ),
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
    response: Response,
) -> ActivityRead:
    response.headers["Cache-Control"] = "private, no-store"
    try:
        return activity_to_read(
            check_in_activity(session, activity_id, current_user.id, payload)
        )
    except ParticipationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
