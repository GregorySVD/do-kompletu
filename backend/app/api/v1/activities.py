from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.activity import (
    ACTIVITY_CATEGORY_MARKDOWN_TABLE,
    ACTIVITY_CREATE_EXAMPLES,
    ActivityCategoryId,
    ActivityCreate,
    ActivityListItem,
    ActivityRead,
    PriceType,
)
from app.services.activity_service import (
    activity_to_list_item,
    activity_to_read,
    create_activity,
    get_activity_by_id,
    list_activities,
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

This milestone supports create, list, and detail operations. Participation,
waitlists, confirmations, check-in, galleries, and nearby-distance calculation are
not implemented. Related response counters and permissions are documented
placeholders.
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
        Body(
            openapi_examples=ACTIVITY_CREATE_EXAMPLES
        ),
    ],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> ActivityRead:
    result = create_activity(session, payload, current_user)
    return activity_to_read(result)


@router.get(
    "",
    response_model=list[ActivityListItem],
    summary="List activities",
    description=(
        "Return public activity cards/map items. Results are stable: active and "
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
    description=(
        "Return public details and the organizer's safe public identity. Password "
        "hashes and other internal user fields are never exposed."
    ),
    response_description="The requested activity details.",
    responses={
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
) -> ActivityRead:
    result = get_activity_by_id(session, activity_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Activity not found",
        )
    return activity_to_read(result)
