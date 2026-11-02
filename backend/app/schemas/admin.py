from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StrictBool

from app.schemas.activity import ActivityOrganizerRead, ActivityStatus


class AdminUserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str
    is_active: bool
    is_admin: bool
    points_total: int
    created_at: datetime


class AdminUserActiveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_active: StrictBool = Field(description="Whether this account may authenticate.")


class AdminActivityRead(BaseModel):
    id: UUID
    title: str
    organizer: ActivityOrganizerRead
    status: ActivityStatus
    start_at: datetime
    end_at: datetime
    cancelled_at: datetime | None
    participant_count: int
    waitlist_count: int
    created_at: datetime
