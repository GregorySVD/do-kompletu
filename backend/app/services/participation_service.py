from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.activity_participation import (
    PARTICIPATION_PRIMARY_KEY,
    ActivityParticipation,
)
from app.services.activity_service import (
    ActivityResult,
    _as_aware_utc,
    get_activity_by_id,
    get_activity_for_update,
)


class ParticipationError(Exception):
    """Expected domain failure, translated to the existing API detail contract."""

    def __init__(self, detail: str, status_code: int = 409):
        super().__init__(detail)
        self.status_code = status_code


def _lock_activity(session: Session, activity_id: UUID, user_id: UUID) -> Activity:
    activity = get_activity_for_update(session, activity_id)
    if activity is None:
        raise ParticipationError("Activity not found", 404)
    if activity.organizer_id == user_id:
        raise ParticipationError("Organizer cannot join or leave their own activity")
    if activity.cancelled_at is not None:
        raise ParticipationError("Activity is cancelled")
    return activity


def _require_open(activity: Activity) -> None:
    # Evaluate time after acquiring the lock, including time spent waiting for it.
    if _as_aware_utc(activity.end_at) <= datetime.now(UTC):
        raise ParticipationError("Activity has ended")


def _snapshot(session: Session, activity_id: UUID, user_id: UUID) -> ActivityResult:
    result = get_activity_by_id(session, activity_id, current_user_id=user_id)
    if result is None:
        raise RuntimeError("Locked activity could not be loaded")
    return result


def join_activity(session: Session, activity_id: UUID, user_id: UUID) -> ActivityResult:
    try:
        activity = _lock_activity(session, activity_id, user_id)
        if session.get(ActivityParticipation, (activity_id, user_id)) is not None:
            raise ParticipationError("Already joined this activity")
        _require_open(activity)
        count = session.scalar(
            select(func.count())
            .select_from(ActivityParticipation)
            .where(ActivityParticipation.activity_id == activity_id)
        )
        if activity.max_participants is not None and count >= activity.max_participants:
            raise ParticipationError("Activity is full")
        session.add(ActivityParticipation(activity_id=activity_id, user_id=user_id))
        session.flush()
        result = _snapshot(session, activity_id, user_id)
        session.commit()
        return result
    except IntegrityError as exc:
        session.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        if constraint == PARTICIPATION_PRIMARY_KEY or (
            "UNIQUE constraint failed: activity_participations.activity_id, "
            "activity_participations.user_id" in str(exc.orig)
        ):
            raise ParticipationError("Already joined this activity") from exc
        raise
    except Exception:
        session.rollback()
        raise


def leave_activity(
    session: Session, activity_id: UUID, user_id: UUID
) -> ActivityResult:
    try:
        activity = _lock_activity(session, activity_id, user_id)
        participation = session.get(ActivityParticipation, (activity_id, user_id))
        if participation is None:
            raise ParticipationError("Not participating in this activity")
        _require_open(activity)
        session.delete(participation)
        session.flush()
        result = _snapshot(session, activity_id, user_id)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
