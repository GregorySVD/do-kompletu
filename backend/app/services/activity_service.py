from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry, WKTElement
from sqlalchemy import Select, case, cast, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.activity import Activity
from app.models.user import User
from app.schemas.activity import (
    ACTIVITY_CATEGORIES,
    ACTIVITY_CATEGORIES_BY_SLUG,
    ActivityCategoryId,
    ActivityCategoryRead,
    ActivityCreate,
    ActivityListItem,
    ActivityOrganizerRead,
    ActivityRead,
    ActivityStatus,
    PriceType,
)


@dataclass(frozen=True, slots=True)
class ActivityResult:
    activity: Activity
    latitude: float
    longitude: float


def create_activity(
    session: Session,
    payload: ActivityCreate,
    organizer: User,
) -> ActivityResult:
    category = ACTIVITY_CATEGORIES[payload.category_id]
    activity = Activity(
        organizer=organizer,
        title=payload.title,
        description=payload.description,
        category=category.slug,
        start_at=payload.start_at,
        end_at=payload.end_at,
        location_name=payload.location_name,
        address=payload.address,
        location=_location_value(session, payload.latitude, payload.longitude),
        min_participants=payload.min_participants,
        max_participants=payload.max_participants,
        price_type=payload.price_type.value,
        price_amount=payload.price_amount,
    )
    session.add(activity)
    session.commit()

    created_activity = get_activity_by_id(session, activity.id)
    if created_activity is None:
        raise RuntimeError("Created activity could not be loaded")
    return created_activity


def list_activities(
    session: Session,
    *,
    limit: int,
    offset: int,
    query: str | None = None,
    category_id: ActivityCategoryId | None = None,
    price_type: PriceType | None = None,
) -> list[ActivityResult]:
    now = datetime.now(UTC)
    statement = select(Activity).options(joinedload(Activity.organizer))

    if query:
        normalized_query = query.strip().lower()
        if normalized_query:
            matching_categories = [
                category.slug
                for category in ACTIVITY_CATEGORIES.values()
                if normalized_query in category.name.casefold()
                or normalized_query in category.slug
            ]
            search_conditions = [
                func.lower(Activity.title).contains(normalized_query, autoescape=True),
                func.lower(Activity.location_name).contains(
                    normalized_query,
                    autoescape=True,
                ),
                func.lower(Activity.address).contains(normalized_query, autoescape=True),
            ]
            if matching_categories:
                search_conditions.append(Activity.category.in_(matching_categories))
            statement = statement.where(or_(*search_conditions))

    if category_id is not None:
        statement = statement.where(
            Activity.category == ACTIVITY_CATEGORIES[category_id].slug
        )
    if price_type is not None:
        statement = statement.where(Activity.price_type == price_type.value)

    statement = statement.order_by(
        case((Activity.end_at >= now, 0), else_=1),
        Activity.start_at.asc(),
        Activity.id.asc(),
    )
    statement = statement.offset(offset).limit(limit)
    return _activity_results(session, statement)


def get_activity_by_id(session: Session, activity_id: UUID) -> ActivityResult | None:
    statement = (
        select(Activity)
        .where(Activity.id == activity_id)
        .options(joinedload(Activity.organizer))
    )
    results = _activity_results(session, statement)
    return results[0] if results else None


def activity_to_list_item(result: ActivityResult) -> ActivityListItem:
    activity = result.activity
    category = ACTIVITY_CATEGORIES_BY_SLUG[activity.category]
    start_at = _as_aware_utc(activity.start_at)
    end_at = _as_aware_utc(activity.end_at)
    participant_count = 0
    available_slots = (
        None
        if activity.max_participants is None
        else activity.max_participants - participant_count
    )

    return ActivityListItem(
        id=activity.id,
        title=activity.title,
        category=ActivityCategoryRead(
            id=UUID(category.id.value),
            name=category.name,
            slug=category.slug,
        ),
        start_at=start_at,
        end_at=end_at,
        location_name=activity.location_name,
        address=activity.address,
        latitude=result.latitude,
        longitude=result.longitude,
        distance_m=None,
        price_type=PriceType(activity.price_type),
        min_participants=activity.min_participants,
        max_participants=activity.max_participants,
        participant_count=participant_count,
        checked_in_count=0,
        waitlist_count=0,
        available_slots=available_slots,
        status=_activity_status(start_at, end_at),
    )


def activity_to_read(result: ActivityResult) -> ActivityRead:
    activity = result.activity
    list_item = activity_to_list_item(result)
    return ActivityRead(
        **list_item.model_dump(),
        description=activity.description,
        organizer=ActivityOrganizerRead(
            id=activity.organizer.id,
            display_name=activity.organizer.display_name,
            avatar_url=activity.organizer.avatar_url,
        ),
        price_amount=(
            float(activity.price_amount) if activity.price_amount is not None else None
        ),
        currency="PLN" if activity.price_type == PriceType.PAID.value else None,
    )


def _activity_results(
    session: Session,
    statement: Select[tuple[Activity]],
) -> list[ActivityResult]:
    if _is_postgresql(session):
        point_geometry = cast(
            Activity.location,
            Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        )
        rows = session.execute(
            statement.add_columns(
                func.ST_Y(point_geometry).label("latitude"),
                func.ST_X(point_geometry).label("longitude"),
            )
        ).unique()
        return [
            ActivityResult(
                activity=row[0],
                latitude=float(row.latitude),
                longitude=float(row.longitude),
            )
            for row in rows
        ]

    activities = session.scalars(statement).unique()
    return [
        ActivityResult(activity=activity, **_parse_test_location(activity.location))
        for activity in activities
    ]


def _location_value(session: Session, latitude: float, longitude: float) -> Any:
    point = f"POINT({longitude} {latitude})"
    if _is_postgresql(session):
        return WKTElement(point, srid=4326)
    return f"SRID=4326;{point}"


def _parse_test_location(location: Any) -> dict[str, float]:
    value = str(location)
    coordinates = value[value.index("POINT(") + 6 : value.rindex(")")]
    longitude, latitude = (float(coordinate) for coordinate in coordinates.split())
    return {"latitude": latitude, "longitude": longitude}


def _is_postgresql(session: Session) -> bool:
    return session.get_bind().dialect.name == "postgresql"


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _activity_status(start_at: datetime, end_at: datetime) -> ActivityStatus:
    now = datetime.now(UTC)
    if now < start_at:
        return ActivityStatus.PUBLISHED
    if now < end_at:
        return ActivityStatus.ONGOING
    return ActivityStatus.ENDED
