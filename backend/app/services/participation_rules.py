from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.models.activity_participation import ActivityParticipation, ParticipationStatus

COMPLETED_ACTIVITY_POINTS = 10

FINALIZATION_TRANSITIONS = {
    ParticipationStatus.JOINED: ParticipationStatus.NO_SHOW,
    ParticipationStatus.CONFIRMED: ParticipationStatus.NO_SHOW,
    ParticipationStatus.CHECKED_IN: ParticipationStatus.COMPLETED,
}


def waitlist_ordering(participation=ActivityParticipation):
    """Canonical FIFO key, shared by promotion and caller-only SQL position."""
    return participation.waitlisted_at, participation.user_id


def _shift_time(value: datetime, duration: timedelta) -> datetime:
    try:
        return value + duration
    except OverflowError:
        return (
            datetime.min.replace(tzinfo=UTC)
            if duration < timedelta(0)
            else datetime.max.replace(tzinfo=UTC)
        )


def confirmation_window(start_at: datetime) -> tuple[datetime, datetime]:
    """Public normal window, independent of caller identity or queue history."""
    settings = get_settings()
    return (
        _shift_time(
            start_at,
            -timedelta(minutes=settings.activity_confirmation_open_minutes_before),
        ),
        _shift_time(
            start_at,
            -timedelta(minutes=settings.activity_confirmation_deadline_minutes_before),
        ),
    )


def effective_confirmation_deadline(
    start_at: datetime, joined_at: datetime
) -> datetime:
    """Actual place acquisition grants grace at/after the normal deadline."""
    _, normal_deadline = confirmation_window(start_at)
    if joined_at < normal_deadline:
        return normal_deadline
    grace = timedelta(minutes=get_settings().activity_late_confirmation_grace_minutes)
    return min(_shift_time(joined_at, grace), start_at)


def is_confirmation_window_open(
    start_at: datetime, joined_at: datetime, now: datetime
) -> bool:
    opens_at, _ = confirmation_window(start_at)
    deadline_at = effective_confirmation_deadline(start_at, joined_at)
    return opens_at <= now < deadline_at


def check_in_window(start_at: datetime, end_at: datetime) -> tuple[datetime, datetime]:
    settings = get_settings()
    opens_at = _shift_time(
        start_at, -timedelta(minutes=settings.activity_check_in_open_minutes_before)
    )
    deadline_at = min(
        end_at,
        _shift_time(
            start_at, timedelta(minutes=settings.activity_check_in_close_minutes_after)
        ),
    )
    return opens_at, deadline_at


def is_check_in_window_open(
    start_at: datetime, end_at: datetime, now: datetime
) -> bool:
    opens_at, deadline_at = check_in_window(start_at, end_at)
    return opens_at <= now < deadline_at
