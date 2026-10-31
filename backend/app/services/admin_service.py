from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.activity import Activity
from app.models.user import User
from app.schemas.activity import ActivityOrganizerRead
from app.schemas.admin import AdminActivityRead, AdminUserRead
from app.services.activity_service import (
    ActivityResult,
    _activity_results,
    _activity_status,
    _as_aware_utc,
)


class AdministrationError(Exception):
    def __init__(self, detail: str, status_code: int):
        super().__init__(detail)
        self.status_code = status_code


def list_users(session: Session, *, limit: int, offset: int) -> list[AdminUserRead]:
    # Select only the moderation fields, never password hashes/auth metadata.
    rows = session.execute(
        select(
            User.id,
            User.email,
            User.display_name,
            User.is_active,
            User.is_admin,
            User.points_total,
            User.created_at,
        )
        .order_by(User.created_at.asc(), User.id.asc())
        .limit(limit)
        .offset(offset)
    ).mappings()
    return [AdminUserRead.model_validate(row) for row in rows]


def set_user_active(
    session: Session, user_id: UUID, admin_id: UUID, *, is_active: bool
) -> User:
    try:
        if user_id == admin_id and not is_active:
            raise AdministrationError(
                "Administrators cannot deactivate themselves", 409
            )
        user = session.get(User, user_id, populate_existing=True)
        if user is None:
            raise AdministrationError("User not found", 404)
        user.is_active = is_active
        session.commit()
        session.refresh(user)
        return user
    except Exception:
        session.rollback()
        raise


def activity_to_admin_read(result: ActivityResult) -> AdminActivityRead:
    activity = result.activity
    start_at, end_at = map(_as_aware_utc, (activity.start_at, activity.end_at))
    return AdminActivityRead(
        id=activity.id,
        title=activity.title,
        organizer=ActivityOrganizerRead.model_validate(
            activity.organizer, from_attributes=True
        ),
        status=_activity_status(
            start_at, end_at, as_of=result.as_of, cancelled_at=activity.cancelled_at
        ),
        start_at=start_at,
        end_at=end_at,
        cancelled_at=(
            _as_aware_utc(activity.cancelled_at)
            if activity.cancelled_at is not None
            else None
        ),
        participant_count=result.participant_count,
        waitlist_count=result.waitlist_count,
        created_at=_as_aware_utc(activity.created_at),
    )


def list_activities(
    session: Session, *, limit: int, offset: int
) -> list[AdminActivityRead]:
    statement = (
        select(Activity)
        .options(joinedload(Activity.organizer))
        .order_by(Activity.created_at.asc(), Activity.id.asc())
        .limit(limit)
        .offset(offset)
    )
    # Shared SQL counts, no discovery filter, no caller membership/permissions.
    return [
        activity_to_admin_read(result)
        for result in _activity_results(session, statement, as_of=datetime.now(UTC))
    ]
