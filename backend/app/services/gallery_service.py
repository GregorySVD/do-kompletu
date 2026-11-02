from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import BinaryIO
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.activity_photo import ActivityPhoto
from app.models.user import User
from app.schemas.activity_photo import ActivityPhotoRead, PhotoUploaderRead
from app.services.activity_service import _as_aware_utc, get_activity_for_update
from app.services.gallery_rules import (
    can_upload_activity_photo,
    can_view_activity_gallery,
    gallery_closes_at,
)
from app.services.photo_storage import PhotoStorage, PhotoStorageError
from app.services.photo_validation import validate_photo

logger = logging.getLogger(__name__)
MAX_PHOTOS_PER_USER = 3


class GalleryError(Exception):
    def __init__(self, detail: str, status_code: int = 403):
        super().__init__(detail)
        self.status_code = status_code


def utc_now() -> datetime:
    return datetime.now(UTC)


def _activity(session: Session, activity_id: UUID, *, lock: bool = False) -> Activity:
    activity = (
        get_activity_for_update(session, activity_id)
        if lock
        else session.get(Activity, activity_id, populate_existing=True)
    )
    if activity is None:
        raise GalleryError("Activity not found", 404)
    return activity


def _authorize(
    session: Session, activity: Activity, user_id: UUID, now: datetime, *, upload=False
) -> None:
    status = session.scalar(
        select(ActivityParticipation.status).where(
            ActivityParticipation.activity_id == activity.id,
            ActivityParticipation.user_id == user_id,
        )
    )
    rule = can_upload_activity_photo if upload else can_view_activity_gallery
    if not rule(activity, user_id, status, now):
        raise GalleryError(
            "Photo upload is not allowed" if upload else "Gallery access is not allowed"
        )


def _photo_read(
    photo: ActivityPhoto, activity: Activity, storage: PhotoStorage, now: datetime
) -> ActivityPhotoRead:
    ttl = min(
        get_settings().s3_presigned_url_ttl_seconds,
        max(1, int((gallery_closes_at(activity) - now).total_seconds())),
    )
    return ActivityPhotoRead(
        id=photo.id,
        activity_id=photo.activity_id,
        uploader=PhotoUploaderRead(
            id=photo.uploader.id,
            display_name=photo.uploader.display_name,
            avatar_url=photo.uploader.avatar_url,
        ),
        created_at=_as_aware_utc(photo.created_at),
        content_type=photo.content_type,
        size_bytes=photo.size_bytes,
        url=storage.presigned_get_url(photo.object_key, ttl),
    )


def list_photos(
    session: Session,
    activity_id: UUID,
    user_id: UUID,
    storage: PhotoStorage,
    *,
    clock: Callable[[], datetime] | None = None,
) -> list[ActivityPhotoRead]:
    activity = _activity(session, activity_id)
    now = (clock or utc_now)()
    _authorize(session, activity, user_id, now)
    photos = session.scalars(
        select(ActivityPhoto)
        .where(ActivityPhoto.activity_id == activity_id)
        .options(
            joinedload(ActivityPhoto.uploader).load_only(
                User.id, User.display_name, User.avatar_url
            )
        )
        .order_by(ActivityPhoto.created_at.asc(), ActivityPhoto.id.asc())
    ).all()
    return [_photo_read(photo, activity, storage, now) for photo in photos]


def upload_photo(
    session: Session,
    activity_id: UUID,
    user_id: UUID,
    file: BinaryIO,
    declared_type: str | None,
    storage: PhotoStorage,
    *,
    clock: Callable[[], datetime] | None = None,
) -> ActivityPhotoRead:
    object_key = None
    try:
        activity = _activity(session, activity_id, lock=True)
        now = (
            clock or utc_now
        )()  # Never use a timestamp captured before lock waiting.
        _authorize(session, activity, user_id, now, upload=True)
        count = session.scalar(
            select(func.count())
            .select_from(ActivityPhoto)
            .where(
                ActivityPhoto.activity_id == activity_id,
                ActivityPhoto.uploader_id == user_id,
            )
        )
        if count >= MAX_PHOTOS_PER_USER:
            raise GalleryError("Maximum 3 photos per user per activity", 409)
        validated = validate_photo(file, declared_type)
        # Image decoding can take time; recheck expiry under the same parent lock.
        now = (clock or utc_now)()
        _authorize(session, activity, user_id, now, upload=True)
        photo_id = uuid4()
        object_key = f"activities/{activity_id}/{photo_id}.{validated.extension}"
        storage.put(object_key, validated.data, validated.content_type)
        photo = ActivityPhoto(
            id=photo_id,
            activity_id=activity_id,
            uploader_id=user_id,
            uploader=session.get(User, user_id),
            object_key=object_key,
            content_type=validated.content_type,
            size_bytes=len(validated.data),
            created_at=now,
        )
        session.add(photo)
        session.flush()
        # Build/sign before commit: failures here still compensate the object.
        now = (clock or utc_now)()
        _authorize(session, activity, user_id, now, upload=True)
        response = _photo_read(photo, activity, storage, now)
        session.commit()
        return response
    except Exception:
        session.rollback()
        if object_key is not None:
            try:
                storage.delete(object_key)
            except PhotoStorageError:
                # No SDK exception text: it can contain request URLs/credentials.
                logger.error(
                    "Gallery upload cleanup failed; orphan object requires cleanup: %s",
                    object_key,
                )
        raise


def delete_photo(
    session: Session,
    activity_id: UUID,
    photo_id: UUID,
    user_id: UUID,
    storage: PhotoStorage,
    *,
    is_admin: bool = False,
    clock: Callable[[], datetime] | None = None,
) -> None:
    storage_deleted = False
    try:
        activity = _activity(session, activity_id, lock=True)
        photo = session.scalar(
            select(ActivityPhoto)
            .where(
                ActivityPhoto.id == photo_id, ActivityPhoto.activity_id == activity_id
            )
            .execution_options(populate_existing=True)
        )
        if photo is None:
            raise GalleryError("Photo not found", 404)
        if photo.uploader_id != user_id and not is_admin:
            raise GalleryError("Only the uploader can delete this photo")
        if not is_admin:
            _authorize(session, activity, user_id, (clock or utc_now)())
        storage.delete(photo.object_key)
        storage_deleted = True
        session.delete(photo)
        session.commit()
    except Exception:
        session.rollback()
        if storage_deleted:
            logger.error(
                "Gallery metadata deletion failed after object removal; retry photo %s",
                photo_id,
            )
        raise
