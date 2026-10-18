from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.activity import Activity
from app.models.activity_participation import (
    ACTIVE_PARTICIPATION_STATUSES,
    PARTICIPATION_PRIMARY_KEY,
    ActivityParticipation,
    ParticipationStatus,
)
from app.schemas.activity_check_in import ActivityCheckIn
from app.services.activity_service import (
    ActivityResult,
    _as_aware_utc,
    get_activity_by_id,
    get_activity_for_update,
)
from app.services.participation_rules import check_in_window, confirmation_window


class ParticipationError(Exception):
    """Expected domain failure, translated to the existing API detail contract."""

    def __init__(self, detail: str, status_code: int = 409):
        super().__init__(detail)
        self.status_code = status_code


def _lock_activity(
    session: Session,
    activity_id: UUID,
    user_id: UUID,
    *,
    organizer_error: str = "Organizer cannot join or leave their own activity",
) -> Activity:
    activity = get_activity_for_update(session, activity_id)
    if activity is None:
        raise ParticipationError("Activity not found", 404)
    if activity.organizer_id == user_id:
        raise ParticipationError(organizer_error)
    if activity.cancelled_at is not None:
        raise ParticipationError("Activity is cancelled")
    return activity


def _require_open(activity: Activity, now: datetime) -> None:
    # Evaluate time after acquiring the lock, including time spent waiting for it.
    if _as_aware_utc(activity.end_at) <= now:
        raise ParticipationError("Activity has ended")


def _snapshot(
    session: Session, activity_id: UUID, user_id: UUID, now: datetime
) -> ActivityResult:
    result = get_activity_by_id(
        session, activity_id, current_user_id=user_id, as_of=now
    )
    if result is None:
        raise RuntimeError("Locked activity could not be loaded")
    return result


def join_activity(session: Session, activity_id: UUID, user_id: UUID) -> ActivityResult:
    try:
        activity = _lock_activity(session, activity_id, user_id)
        participation = session.get(
            ActivityParticipation, (activity_id, user_id), populate_existing=True
        )
        if (
            participation is not None
            and participation.status in ACTIVE_PARTICIPATION_STATUSES
        ):
            raise ParticipationError("Already joined this activity")
        now = datetime.now(UTC)
        _require_open(activity, now)
        count = session.scalar(
            select(func.count())
            .select_from(ActivityParticipation)
            .where(
                ActivityParticipation.activity_id == activity_id,
                ActivityParticipation.status.in_(ACTIVE_PARTICIPATION_STATUSES),
            )
        )
        if activity.max_participants is not None and count >= activity.max_participants:
            raise ParticipationError("Activity is full")
        if participation is None:
            participation = ActivityParticipation(
                activity_id=activity_id, user_id=user_id
            )
            session.add(participation)
        participation.status = ParticipationStatus.JOINED
        participation.joined_at = now
        participation.left_at = None
        participation.confirmed_at = None
        participation.checked_in_at = None
        session.flush()
        result = _snapshot(session, activity_id, user_id, now)
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
        participation = session.get(
            ActivityParticipation, (activity_id, user_id), populate_existing=True
        )
        if (
            participation is None
            or participation.status not in ACTIVE_PARTICIPATION_STATUSES
        ):
            raise ParticipationError("Not participating in this activity")
        now = datetime.now(UTC)
        _require_open(activity, now)
        if participation.status == ParticipationStatus.CHECKED_IN:
            raise ParticipationError("Checked-in participants cannot leave")
        participation.status = ParticipationStatus.LEFT
        participation.left_at = now
        # Retain joined_at and any confirmed_at as evidence of the last cycle.
        session.flush()
        result = _snapshot(session, activity_id, user_id, now)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def confirm_activity(
    session: Session, activity_id: UUID, user_id: UUID
) -> ActivityResult:
    try:
        activity = _lock_activity(
            session,
            activity_id,
            user_id,
            organizer_error="Organizer cannot confirm their own activity",
        )
        now = datetime.now(UTC)
        _require_open(activity, now)
        participation = session.get(
            ActivityParticipation, (activity_id, user_id), populate_existing=True
        )
        if (
            participation is None
            or participation.status not in ACTIVE_PARTICIPATION_STATUSES
        ):
            raise ParticipationError("Not participating in this activity")
        if participation.status == ParticipationStatus.CHECKED_IN:
            raise ParticipationError("Already checked in")
        if participation.status == ParticipationStatus.CONFIRMED:
            raise ParticipationError("Already confirmed attendance")
        opens_at, deadline_at = confirmation_window(_as_aware_utc(activity.start_at))
        if now < opens_at:
            raise ParticipationError("Confirmation window has not opened")
        if now >= deadline_at:
            raise ParticipationError("Confirmation window has closed")
        participation.status = ParticipationStatus.CONFIRMED
        participation.confirmed_at = now
        session.flush()
        result = _snapshot(session, activity_id, user_id, now)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def _within_check_in_radius(
    session: Session, activity_id: UUID, payload: ActivityCheckIn, radius: int
) -> bool:
    if session.get_bind().dialect.name != "postgresql":
        # No approximate SQLite/Python fallback may authorize attendance.
        raise ParticipationError("Check-in requires PostgreSQL/PostGIS", 503)
    submitted_point = cast(
        func.ST_SetSRID(func.ST_MakePoint(payload.longitude, payload.latitude), 4326),
        Geography(geometry_type="POINT", srid=4326, spatial_index=False),
    )
    return bool(
        session.scalar(
            select(
                func.ST_DWithin(Activity.location, submitted_point, radius, True)
            ).where(Activity.id == activity_id)
        )
    )


def check_in_activity(
    session: Session, activity_id: UUID, user_id: UUID, payload: ActivityCheckIn
) -> ActivityResult:
    try:
        activity = _lock_activity(
            session,
            activity_id,
            user_id,
            organizer_error="Organizer cannot check in to their own activity",
        )
        now = datetime.now(UTC)
        _require_open(activity, now)
        participation = session.get(
            ActivityParticipation, (activity_id, user_id), populate_existing=True
        )
        if (
            participation is None
            or participation.status not in ACTIVE_PARTICIPATION_STATUSES
        ):
            raise ParticipationError("Not participating in this activity")
        if participation.status == ParticipationStatus.CHECKED_IN:
            raise ParticipationError("Already checked in")
        if participation.status != ParticipationStatus.CONFIRMED:
            raise ParticipationError("Attendance must be confirmed before check-in")
        opens_at, deadline_at = check_in_window(
            _as_aware_utc(activity.start_at), _as_aware_utc(activity.end_at)
        )
        if now < opens_at:
            raise ParticipationError("Check-in window has not opened")
        if now >= deadline_at:
            raise ParticipationError("Check-in window has closed")
        if not _within_check_in_radius(
            session,
            activity_id,
            payload,
            get_settings().activity_check_in_radius_meters,
        ):
            raise ParticipationError("Outside check-in radius")
        participation.status = ParticipationStatus.CHECKED_IN
        participation.checked_in_at = now
        session.flush()
        result = _snapshot(session, activity_id, user_id, now)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
