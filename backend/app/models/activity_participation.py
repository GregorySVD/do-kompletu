from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    PrimaryKeyConstraint,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base

PARTICIPATION_PRIMARY_KEY = "pk_activity_participations"
PARTICIPATION_STATUS_CHECK = "ck_activity_participations_status"
PARTICIPATION_TIMESTAMPS_CHECK = "ck_activity_participations_state_timestamps"


class ParticipationStatus(StrEnum):
    WAITLISTED = "WAITLISTED"
    JOINED = "JOINED"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    COMPLETED = "COMPLETED"
    NO_SHOW = "NO_SHOW"
    LEFT = "LEFT"


# Current occupancy and final history are distinct concepts.
CAPACITY_CONSUMING_STATES = (
    ParticipationStatus.JOINED,
    ParticipationStatus.CONFIRMED,
    ParticipationStatus.CHECKED_IN,
)
CURRENT_PARTICIPATION_STATES = CAPACITY_CONSUMING_STATES
WAITLIST_STATES = (ParticipationStatus.WAITLISTED,)
REQUESTED_PARTICIPATION_STATES = CURRENT_PARTICIPATION_STATES + WAITLIST_STATES
LEAVABLE_PARTICIPATION_STATES = (
    ParticipationStatus.JOINED,
    ParticipationStatus.CONFIRMED,
) + WAITLIST_STATES
ACTIVE_PARTICIPATION_STATUSES = (
    CAPACITY_CONSUMING_STATES  # Existing internal import compatibility.
)
FINAL_ATTENDANCE_STATES = (ParticipationStatus.COMPLETED, ParticipationStatus.NO_SHOW)
PARTICIPATION_HISTORY_STATES = CURRENT_PARTICIPATION_STATES + FINAL_ATTENDANCE_STATES
VISIBLE_PARTICIPATION_STATES = PARTICIPATION_HISTORY_STATES + WAITLIST_STATES
CHECKED_IN_PARTICIPATION_STATES = (
    ParticipationStatus.CHECKED_IN,
    ParticipationStatus.COMPLETED,
)
SCHEDULE_PROTECTED_PARTICIPATION_STATUSES = (
    ParticipationStatus.CONFIRMED,
    ParticipationStatus.CHECKED_IN,
    ParticipationStatus.COMPLETED,
)


class ActivityParticipation(Base):
    """One retained row per user/activity; status determines active membership."""

    __tablename__ = "activity_participations"

    activity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("activities.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    joined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True).evaluates_none(),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=True,
    )
    waitlisted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(
        String(16),
        default=ParticipationStatus.JOINED,
        server_default=ParticipationStatus.JOINED.value,
        nullable=False,
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    no_show_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        PrimaryKeyConstraint("activity_id", "user_id", name=PARTICIPATION_PRIMARY_KEY),
        CheckConstraint(
            "status IN ('WAITLISTED', 'JOINED', 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW', 'LEFT')",
            name=PARTICIPATION_STATUS_CHECK,
        ),
        CheckConstraint(
            "(status = 'WAITLISTED' AND waitlisted_at IS NOT NULL AND joined_at IS NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
            "(status = 'JOINED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
            "(status = 'CONFIRMED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
            "(status = 'CHECKED_IN' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
            "(status = 'COMPLETED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NOT NULL AND no_show_at IS NULL) OR "
            "(status = 'NO_SHOW' AND joined_at IS NOT NULL AND left_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NOT NULL) OR "
            "(status = 'LEFT' AND (joined_at IS NOT NULL OR (waitlisted_at IS NOT NULL AND confirmed_at IS NULL)) AND left_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL)",
            name=PARTICIPATION_TIMESTAMPS_CHECK,
        ),
        Index("ix_activity_participations_user_id", "user_id"),
        Index(
            "ix_activity_participations_fifo",
            "activity_id",
            "status",
            "waitlisted_at",
            "user_id",
        ),
    )
