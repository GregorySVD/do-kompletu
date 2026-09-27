from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from geoalchemy2 import Geography
from geoalchemy2.elements import WKBElement
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


ACTIVITY_CATEGORY_CHECK = "ck_activities_category"
ACTIVITY_PARTICIPANTS_CHECK = "ck_activities_participant_limits"
ACTIVITY_PRICE_CHECK = "ck_activities_price"
ACTIVITY_PRICE_TYPE_CHECK = "ck_activities_price_type"
ACTIVITY_TIME_CHECK = "ck_activities_time_range"

LOCATION_TYPE = Geography(
    geometry_type="POINT",
    srid=4326,
    spatial_index=False,
).with_variant(String(100), "sqlite")


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    organizer_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    location_name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[WKBElement | str] = mapped_column(LOCATION_TYPE, nullable=False)
    min_participants: Mapped[int] = mapped_column(Integer, nullable=False)
    max_participants: Mapped[int | None] = mapped_column(Integer, nullable=True)
    price_type: Mapped[str] = mapped_column(String(10), nullable=False)
    price_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    organizer: Mapped[User] = relationship(back_populates="organized_activities")

    __table_args__ = (
        CheckConstraint("end_at > start_at", name=ACTIVITY_TIME_CHECK),
        CheckConstraint(
            "min_participants BETWEEN 2 AND 100 "
            "AND (max_participants IS NULL "
            "OR max_participants BETWEEN min_participants AND 100)",
            name=ACTIVITY_PARTICIPANTS_CHECK,
        ),
        CheckConstraint(
            "price_type IN ('FREE', 'PAID')",
            name=ACTIVITY_PRICE_TYPE_CHECK,
        ),
        CheckConstraint(
            "(price_type = 'FREE' AND price_amount IS NULL) "
            "OR (price_type = 'PAID' AND price_amount > 0)",
            name=ACTIVITY_PRICE_CHECK,
        ),
        CheckConstraint(
            "category IN ("
            "'sport-zespolowy', 'gry-planszowe', 'rpg', 'gaming', "
            "'wspolna-nauka', 'technologia', 'muzyka', 'kreatywne'"
            ")",
            name=ACTIVITY_CATEGORY_CHECK,
        ),
        Index("ix_activities_organizer_id", "organizer_id"),
        Index("ix_activities_start_at", "start_at"),
        Index("ix_activities_category", "category"),
        Index("ix_activities_location", "location", postgresql_using="gist"),
    )
