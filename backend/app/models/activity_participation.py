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
    JOINED = "JOINED"
    CONFIRMED = "CONFIRMED"
    CHECKED_IN = "CHECKED_IN"
    LEFT = "LEFT"


# All capacity, membership, and personal-list queries share this definition.
ACTIVE_PARTICIPATION_STATUSES = (
    ParticipationStatus.JOINED,
    ParticipationStatus.CONFIRMED,
    ParticipationStatus.CHECKED_IN,
)
SCHEDULE_PROTECTED_PARTICIPATION_STATUSES = (
    ParticipationStatus.CONFIRMED,
    ParticipationStatus.CHECKED_IN,
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
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        default=ParticipationStatus.JOINED,
        server_default=ParticipationStatus.JOINED.value,
        nullable=False,
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        PrimaryKeyConstraint("activity_id", "user_id", name=PARTICIPATION_PRIMARY_KEY),
        CheckConstraint(
            "status IN ('JOINED', 'CONFIRMED', 'CHECKED_IN', 'LEFT')",
            name=PARTICIPATION_STATUS_CHECK,
        ),
        CheckConstraint(
            "(status = 'JOINED' AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL) OR "
            "(status = 'CONFIRMED' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NULL) OR "
            "(status = 'CHECKED_IN' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL) OR "
            "(status = 'LEFT' AND left_at IS NOT NULL AND checked_in_at IS NULL)",
            name=PARTICIPATION_TIMESTAMPS_CHECK,
        ),
        Index("ix_activity_participations_user_id", "user_id"),
    )
