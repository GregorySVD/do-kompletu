from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from geoalchemy2 import Geometry, WKTElement
from sqlalchemy import DateTime, Select, case, cast, func, literal, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import (
    ACTIVITY_CATEGORIES,
    ACTIVITY_CATEGORIES_BY_SLUG,
    ActivityCategoryId,
    ActivityCategoryRead,
    ActivityCreate,
    ActivityListItem,
    ActivityOrganizerRead,
    ActivityParticipationRead,
    ActivityPermissionsRead,
    ActivityRead,
    ActivityStatus,
    PriceType,
)
from app.schemas.my_activities import ActivityRelation, ActivityScope


@dataclass(frozen=True, slots=True)
class ActivityResult:
    activity: Activity
    latitude: float
    longitude: float
    participant_count: int
    current_user_joined_at: datetime | None = None
    current_user_id: UUID | None = None
    as_of: datetime | None = None


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

    created_activity = get_activity_by_id(
        session, activity.id, current_user_id=organizer.id
    )
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
    statement = (
        select(Activity)
        .where(Activity.cancelled_at.is_(None))
        .options(joinedload(Activity.organizer))
    )

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
                func.lower(Activity.address).contains(
                    normalized_query, autoescape=True
                ),
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
        case((Activity.end_at > now, 0), else_=1),
        Activity.start_at.asc(),
        Activity.id.asc(),
    )
    statement = statement.offset(offset).limit(limit)
    return _activity_results(session, statement, as_of=now)


def list_user_activities(
    session: Session,
    *,
    current_user_id: UUID,
    relation: ActivityRelation,
    scope: ActivityScope | None,
    limit: int,
    offset: int,
) -> list[ActivityResult]:
    # One cutoff drives both filtering and response status/permissions, so an
    # activity cannot cross the boundary midway through serializing this page.
    now = datetime.now(UTC)
    statement = select(Activity).options(joinedload(Activity.organizer))
    if relation == ActivityRelation.ORGANIZED:
        statement = statement.where(Activity.organizer_id == current_user_id)
    else:
        membership = (
            select(ActivityParticipation.activity_id)
            .where(
                ActivityParticipation.activity_id == Activity.id,
                ActivityParticipation.user_id == current_user_id,
            )
            .exists()
        )
        statement = statement.where(
            membership, Activity.organizer_id != current_user_id
        )

    if scope == ActivityScope.UPCOMING:
        statement = statement.where(Activity.end_at > now).order_by(
            Activity.start_at.asc(), Activity.id.asc()
        )
    elif scope == ActivityScope.HISTORY:
        statement = statement.where(Activity.end_at <= now).order_by(
            Activity.end_at.desc(), Activity.id.asc()
        )
    else:
        statement = statement.order_by(
            case((Activity.end_at > now, 0), else_=1),
            case((Activity.end_at > now, Activity.start_at)).asc(),
            case((Activity.end_at <= now, Activity.end_at)).desc(),
            Activity.id.asc(),
        )

    return _activity_results(
        session,
        statement.limit(limit).offset(offset),
        current_user_id=current_user_id,
        as_of=now,
    )


def get_activity_for_update(session: Session, activity_id: UUID) -> Activity | None:
    # Every membership/management writer takes this parent lock first. READ
    # COMMITTED ensures queries after acquiring it see the previous writer's commit.
    # Avoid joins/aggregates in the locking SELECT, and refresh cached ORM state.
    return session.scalar(
        select(Activity)
        .where(Activity.id == activity_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def get_activity_by_id(
    session: Session,
    activity_id: UUID,
    *,
    current_user_id: UUID | None = None,
    as_of: datetime | None = None,
) -> ActivityResult | None:
    statement = (
        select(Activity)
        .where(Activity.id == activity_id)
        .options(joinedload(Activity.organizer))
    )
    results = _activity_results(
        session,
        statement,
        current_user_id=current_user_id,
        as_of=as_of if as_of is not None else datetime.now(UTC),
    )
    return results[0] if results else None


def activity_to_list_item(result: ActivityResult) -> ActivityListItem:
    activity = result.activity
    category = ACTIVITY_CATEGORIES_BY_SLUG[activity.category]
    start_at = _as_aware_utc(activity.start_at)
    end_at = _as_aware_utc(activity.end_at)
    participant_count = result.participant_count
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
        status=_activity_status(
            start_at, end_at, as_of=result.as_of, cancelled_at=activity.cancelled_at
        ),
    )


def activity_to_read(result: ActivityResult) -> ActivityRead:
    activity = result.activity
    list_item = activity_to_list_item(result)
    is_participant = result.current_user_joined_at is not None
    eligible_user = (
        result.current_user_id is not None
        and result.current_user_id != activity.organizer_id
    )
    is_open = list_item.status in {ActivityStatus.PUBLISHED, ActivityStatus.ONGOING}
    is_organizer = result.current_user_id == activity.organizer_id
    return ActivityRead(
        **list_item.model_dump(),
        cancelled_at=_as_aware_utc(activity.cancelled_at)
        if activity.cancelled_at is not None
        else None,
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
        current_user_participation=(
            ActivityParticipationRead(
                joined_at=_as_aware_utc(result.current_user_joined_at)
            )
            if result.current_user_joined_at is not None
            else None
        ),
        permissions=ActivityPermissionsRead(
            can_edit=is_organizer and list_item.status == ActivityStatus.PUBLISHED,
            can_cancel=is_organizer and is_open,
            can_join=(
                eligible_user
                and is_open
                and not is_participant
                and (list_item.available_slots is None or list_item.available_slots > 0)
            ),
            can_leave=eligible_user and is_open and is_participant,
        ),
    )


def _activity_results(
    session: Session,
    statement: Select[tuple[Activity]],
    *,
    current_user_id: UUID | None = None,
    as_of: datetime | None = None,
) -> list[ActivityResult]:
    # Correlated projections keep count and caller state in the same SQL snapshot,
    # without loading participant lists or issuing one query per activity.
    participant_count = (
        select(func.count(ActivityParticipation.user_id))
        .where(ActivityParticipation.activity_id == Activity.id)
        .correlate(Activity)
        .scalar_subquery()
    )
    joined_at = (
        select(ActivityParticipation.joined_at)
        .where(
            ActivityParticipation.activity_id == Activity.id,
            ActivityParticipation.user_id == current_user_id,
        )
        .correlate(Activity)
        .scalar_subquery()
        if current_user_id is not None
        else literal(None, type_=DateTime(timezone=True))
    )
    statement = statement.add_columns(
        participant_count.label("participant_count"), joined_at.label("joined_at")
    )
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
                participant_count=row.participant_count,
                current_user_joined_at=row.joined_at,
                current_user_id=current_user_id,
                as_of=as_of,
            )
            for row in rows
        ]

    rows = session.execute(statement).unique()
    return [
        ActivityResult(
            activity=row[0],
            **_parse_test_location(row[0].location),
            participant_count=row.participant_count,
            current_user_joined_at=row.joined_at,
            current_user_id=current_user_id,
            as_of=as_of,
        )
        for row in rows
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


def _activity_status(
    start_at: datetime,
    end_at: datetime,
    *,
    as_of: datetime | None = None,
    cancelled_at: datetime | None = None,
) -> ActivityStatus:
    if cancelled_at is not None:
        return ActivityStatus.CANCELLED
    now = as_of if as_of is not None else datetime.now(UTC)
    if now < start_at:
        return ActivityStatus.PUBLISHED
    if now < end_at:
        return ActivityStatus.ONGOING
    return ActivityStatus.ENDED
