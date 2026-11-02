from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class PhotoUploaderRead(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None


class ActivityPhotoRead(BaseModel):
    id: UUID
    activity_id: UUID
    uploader: PhotoUploaderRead
    created_at: datetime
    content_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int
    url: str
