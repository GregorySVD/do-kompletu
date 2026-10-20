from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.activity_participation import (
    CAPACITY_CONSUMING_STATES,
    WAITLIST_STATES,
    ActivityParticipation,
    ParticipationStatus,
)
from app.services.activity_service import _as_aware_utc
from app.services.participation_rules import waitlist_ordering


def active_participant_count(session: Session, activity: Activity) -> int:
    return session.scalar(
        select(func.count())
        .select_from(ActivityParticipation)
        .where(
            ActivityParticipation.activity_id == activity.id,
            ActivityParticipation.status.in_(CAPACITY_CONSUMING_STATES),
        )
    )


def promote_waitlisted_participants(
    session: Session, activity: Activity, now: datetime
) -> int:
    """Caller MUST hold the refreshed activity-row lock and flush pending changes.

    Never commits or acquires a participation-first lock. All selected rows are
    promoted in one UPDATE, within the caller's leave/edit transaction.
    """
    if activity.cancelled_at is not None or now >= _as_aware_utc(activity.start_at):
        return 0
    candidates = (
        select(ActivityParticipation.user_id)
        .where(
            ActivityParticipation.activity_id == activity.id,
            ActivityParticipation.status.in_(WAITLIST_STATES),
        )
        .order_by(*waitlist_ordering())
    )
    if activity.max_participants is not None:
        available = activity.max_participants - active_participant_count(
            session, activity
        )
        if available <= 0:
            return 0
        candidates = candidates.limit(available)
    result = session.execute(
        update(ActivityParticipation)
        .where(
            ActivityParticipation.activity_id == activity.id,
            ActivityParticipation.user_id.in_(candidates),
            ActivityParticipation.status.in_(WAITLIST_STATES),
        )
        .values(status=ParticipationStatus.JOINED, joined_at=now)
        .execution_options(synchronize_session=False)
    )
    return result.rowcount
