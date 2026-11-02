from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import case, update
from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation, ParticipationStatus
from app.models.user import User
from app.schemas.activity import (
    ACTIVITY_CATEGORIES,
    ACTIVITY_CATEGORIES_BY_SLUG,
    ActivityCreate,
)
from app.schemas.activity_management import ActivityUpdate
from app.services.activity_service import (
    ActivityResult,
    _as_aware_utc,
    _location_value,
    get_activity_by_id,
    get_activity_for_update,
)
from app.services.participation_rules import (
    COMPLETED_ACTIVITY_POINTS,
    FINALIZATION_TRANSITIONS,
)
from app.services.waitlist_service import promote_waitlisted_participants


class ActivityManagementError(Exception):
    def __init__(self, detail: str, status_code: int = 409):
        super().__init__(detail)
        self.status_code = status_code


def _owned_activity(
    session: Session, activity_id: UUID, user_id: UUID, *, is_admin: bool = False
) -> Activity:
    activity = get_activity_for_update(session, activity_id)
    if activity is None:
        raise ActivityManagementError("Activity not found", 404)
    if activity.organizer_id != user_id and not is_admin:
        raise ActivityManagementError(
            "Only the organizer can manage this activity", 403
        )
    if activity.cancelled_at is not None:
        raise ActivityManagementError("Activity is cancelled")
    return activity


def _snapshot(
    session: Session, activity_id: UUID, user_id: UUID, now: datetime
) -> ActivityResult:
    result = get_activity_by_id(
        session, activity_id, current_user_id=user_id, as_of=now
    )
    if result is None:
        raise RuntimeError("Locked activity could not be loaded")
    return result


def update_activity(
    session: Session, activity_id: UUID, user_id: UUID, payload: ActivityUpdate
) -> ActivityResult:
    try:
        activity = _owned_activity(session, activity_id, user_id)
        now = datetime.now(UTC)  # After any time spent waiting for the row lock.
        if _as_aware_utc(activity.start_at) <= now:
            raise ActivityManagementError(
                "Activity can only be edited before it starts"
            )
        before = _snapshot(session, activity_id, user_id, now)
        special = {"category_id", "latitude", "longitude", "has_participant_limit"}
        merged = {
            name: getattr(activity, name)
            for name in ActivityCreate.model_fields
            if name not in special
        }
        merged.update(
            category_id=ACTIVITY_CATEGORIES_BY_SLUG[activity.category].id,
            start_at=_as_aware_utc(activity.start_at),
            end_at=_as_aware_utc(activity.end_at),
            latitude=before.latitude,
            longitude=before.longitude,
            has_participant_limit=activity.max_participants is not None,
        )
        merged.update(payload.model_dump(exclude_unset=True))
        # Reuse the complete creation contract for all merged cross-field rules.
        validated = ActivityCreate.model_validate(merged)
        if validated.start_at <= now:
            raise ActivityManagementError(
                "start_at must remain strictly in the future", 422
            )
        schedule_changed = validated.start_at != _as_aware_utc(
            activity.start_at
        ) or validated.end_at != _as_aware_utc(activity.end_at)
        if schedule_changed and before.schedule_protected_participant_count:
            raise ActivityManagementError(
                "Cannot change schedule while participants are confirmed"
            )
        location_changed = (
            validated.latitude != before.latitude
            or validated.longitude != before.longitude
            or validated.location_name != activity.location_name
            or validated.address != activity.address
        )
        if location_changed and before.checked_in_count:
            raise ActivityManagementError(
                "Cannot change location after participants have checked in"
            )
        if (
            validated.max_participants is not None
            and validated.max_participants < before.participant_count
        ):
            raise ActivityManagementError(
                "Participant limit cannot be below current participant count"
            )
        for name in payload.model_fields_set - special:
            setattr(activity, name, getattr(validated, name))
        if "category_id" in payload.model_fields_set:
            activity.category = ACTIVITY_CATEGORIES[validated.category_id].slug
        if {"latitude", "longitude"} & payload.model_fields_set:
            activity.location = _location_value(
                session, validated.latitude, validated.longitude
            )
        session.flush()
        if {"max_participants", "has_participant_limit"} & payload.model_fields_set:
            promote_waitlisted_participants(session, activity, now)
        result = _snapshot(session, activity_id, user_id, now)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def cancel_activity(
    session: Session, activity_id: UUID, user_id: UUID, *, is_admin: bool = False
) -> ActivityResult:
    try:
        # Only the trusted admin route supplies this privilege. Domain rules and
        # the activity-first lock are shared with ordinary organizer cancellation.
        activity = _owned_activity(session, activity_id, user_id, is_admin=is_admin)
        now = datetime.now(UTC)
        if _as_aware_utc(activity.end_at) <= now:
            raise ActivityManagementError("Activity has ended")
        activity.cancelled_at = now
        session.flush()
        result = _snapshot(session, activity_id, user_id, now)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def finalize_activity(
    session: Session, activity_id: UUID, user_id: UUID
) -> ActivityResult:
    try:
        activity = _owned_activity(session, activity_id, user_id)
        now = datetime.now(UTC)  # Capture after waiting for the same parent-row lock.
        if now < _as_aware_utc(activity.end_at):
            raise ActivityManagementError(
                "Activity can only be finalized after it ends"
            )
        status = ActivityParticipation.status
        checked_in = status == ParticipationStatus.CHECKED_IN
        transitions = session.execute(
            update(ActivityParticipation)
            .where(
                ActivityParticipation.activity_id == activity_id,
                status.in_(tuple(FINALIZATION_TRANSITIONS)),
            )
            .values(
                status=case(
                    *[
                        (status == source, target.value)
                        for source, target in FINALIZATION_TRANSITIONS.items()
                    ]
                ),
                completed_at=case((checked_in, now), else_=None),
                no_show_at=case((checked_in, None), else_=now),
            )
            .returning(ActivityParticipation.user_id, ActivityParticipation.status)
            .execution_options(synchronize_session=False)
        ).all()
        if not transitions:
            raise ActivityManagementError("No unresolved attendance to finalize")
        # RETURNING contains only rows changed by this transaction, never prior
        # COMPLETED outcomes. The parent lock serializes retries for this activity.
        completed_users = [
            row.user_id
            for row in transitions
            if row.status == ParticipationStatus.COMPLETED
        ]
        if completed_users:
            # SQL arithmetic preserves balances, including concurrent completion
            # of another activity. Account deactivation does not erase attendance.
            session.execute(
                update(User)
                .where(User.id.in_(completed_users))
                .values(points_total=User.points_total + COMPLETED_ACTIVITY_POINTS)
                .execution_options(synchronize_session=False)
            )
        # Attendance and points commit together. Response SQL reads database state.
        snapshot = _snapshot(session, activity_id, user_id, now)
        session.commit()
        return snapshot
    except Exception:
        session.rollback()
        raise
