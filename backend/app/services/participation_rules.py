from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.core.config import get_settings
from app.models.activity_participation import ActivityParticipation, ParticipationStatus

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
    """Nominal UTC window: inclusive opening, exclusive deadline at start."""
    duration = timedelta(hours=get_settings().activity_confirmation_window_hours)
    return _shift_time(start_at, -duration), start_at


def is_confirmation_window_open(start_at: datetime, now: datetime) -> bool:
    opens_at, deadline_at = confirmation_window(start_at)
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
