from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.activity import Activity

DISPLAY_NAME_UNIQUE_INDEX = "uq_users_display_name_lower"
EMAIL_UNIQUE_CONSTRAINT = "uq_users_email"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    points_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    organized_activities: Mapped[list[Activity]] = relationship(
        back_populates="organizer",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("email", name=EMAIL_UNIQUE_CONSTRAINT),
        Index(DISPLAY_NAME_UNIQUE_INDEX, func.lower(display_name), unique=True),
    )
