from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.models.activity import Activity
from app.models.activity_participation import (
    WAITLIST_STATES,
    ActivityParticipation,
    ParticipationStatus,
)
from app.services.activity_service import _as_aware_utc, get_activity_for_update
from app.services.participation_rules import (
    _shift_time,
    effective_confirmation_deadline,
)
from app.services.waitlist_service import promote_waitlisted_participants

logger = logging.getLogger(__name__)


@dataclass
class LifecycleSweepResult:
    activities_processed: int = 0
    confirmation_expired: int = 0
    promoted: int = 0
    waitlist_expired: int = 0
    failed: int = 0


def reconcile_activity_participation(
    session: Session, activity: Activity, now: datetime
) -> LifecycleSweepResult:
    """Caller holds the refreshed activity-first lock. No independent commit."""
    result = LifecycleSweepResult()
    if activity.cancelled_at is not None:
        return result
    start = _as_aware_utc(activity.start_at)
    # One projection, then a bulk update: no SELECT per participant. Only JOINED
    # requires Python deadline evaluation; existing activity/status index applies.
    joined = session.execute(
        select(ActivityParticipation.user_id, ActivityParticipation.joined_at).where(
            ActivityParticipation.activity_id == activity.id,
            ActivityParticipation.status == ParticipationStatus.JOINED,
        )
    )
    due_users = [
        row.user_id
        for row in joined
        if now >= effective_confirmation_deadline(start, _as_aware_utc(row.joined_at))
    ]
    if due_users:
        changed = session.execute(
            update(ActivityParticipation)
            .where(
                ActivityParticipation.activity_id == activity.id,
                ActivityParticipation.user_id.in_(due_users),
                ActivityParticipation.status == ParticipationStatus.JOINED,
            )
            .values(
                status=ParticipationStatus.CONFIRMATION_EXPIRED,
                confirmation_expired_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        result.confirmation_expired = changed.rowcount
    if now >= start:
        changed = session.execute(
            update(ActivityParticipation)
            .where(
                ActivityParticipation.activity_id == activity.id,
                ActivityParticipation.status.in_(WAITLIST_STATES),
            )
            .values(
                status=ParticipationStatus.WAITLIST_EXPIRED, waitlist_expired_at=now
            )
            .execution_options(synchronize_session=False)
        )
        result.waitlist_expired = changed.rowcount
    elif result.confirmation_expired:
        result.promoted = promote_waitlisted_participants(session, activity, now)
    return result


def run_participation_lifecycle_sweep(
    session_factory: Callable[[], Session] | None = None, *, now: datetime | None = None
) -> LifecycleSweepResult:
    """Find candidates without locks, then commit each refreshed activity atomically.

    Explicit time is for deterministic tests/operations. Production captures time
    again AFTER obtaining each activity lock, including any time spent waiting.
    A failed activity rolls back and is logged; unrelated candidates continue.
    """
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError("Lifecycle sweep time must be timezone-aware")
    if now is not None:
        now = now.astimezone(UTC)
    factory = session_factory if session_factory is not None else get_session_factory()
    cutoff = now if now is not None else datetime.now(UTC)
    horizon = _shift_time(
        cutoff,
        timedelta(minutes=get_settings().activity_confirmation_deadline_minutes_before),
    )
    relevant_participation = (
        select(ActivityParticipation.user_id)
        .where(
            ActivityParticipation.activity_id == Activity.id,
            or_(
                ActivityParticipation.status == ParticipationStatus.JOINED,
                (ActivityParticipation.status.in_(WAITLIST_STATES))
                & (Activity.start_at <= cutoff),
            ),
        )
        .exists()
    )
    with factory() as session:
        candidates = list(
            session.scalars(
                select(Activity.id)
                .where(
                    Activity.cancelled_at.is_(None),
                    Activity.start_at <= horizon,
                    relevant_participation,
                )
                .order_by(Activity.start_at, Activity.id)
            )
        )
    total = LifecycleSweepResult()
    for activity_id in candidates:
        try:
            with factory() as session, session.begin():
                activity = get_activity_for_update(session, activity_id)
                if activity is None or activity.cancelled_at is not None:
                    continue
                activity_now = now if now is not None else datetime.now(UTC)
                changed = reconcile_activity_participation(
                    session, activity, activity_now
                )
            # Do not count rolled-back work as successful.
            total.activities_processed += 1
            total.confirmation_expired += changed.confirmation_expired
            total.promoted += changed.promoted
            total.waitlist_expired += changed.waitlist_expired
        except Exception:
            total.failed += 1
            logger.exception(
                "Participation lifecycle failed for activity %s", activity_id
            )
    return total
