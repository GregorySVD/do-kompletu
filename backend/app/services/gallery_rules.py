"""Shared gallery eligibility for ActivityRead and protected photo operations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.models.activity import Activity
from app.models.activity_participation import CHECKED_IN_PARTICIPATION_STATES
from app.services.participation_rules import _shift_time


def gallery_closes_at(activity: Activity) -> datetime:
    end = activity.end_at
    # SQLite fixtures lose timezone information; persisted PostgreSQL values do not.
    end = end.replace(tzinfo=UTC) if end.tzinfo is None else end.astimezone(UTC)
    return _shift_time(end, timedelta(hours=72))


def can_view_activity_gallery(
    activity: Activity, user_id: UUID | None, status: str | None, now: datetime
) -> bool:
    return (
        user_id is not None
        and now < gallery_closes_at(activity)
        and (
            user_id == activity.organizer_id
            or status in CHECKED_IN_PARTICIPATION_STATES
        )
    )


def can_upload_activity_photo(
    activity: Activity, user_id: UUID | None, status: str | None, now: datetime
) -> bool:
    return (
        can_view_activity_gallery(activity, user_id, status, now)
        and status in CHECKED_IN_PARTICIPATION_STATES
        and activity.cancelled_at is None
    )
