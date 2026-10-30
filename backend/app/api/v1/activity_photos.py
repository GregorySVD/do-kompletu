from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.activity_photo import ActivityPhotoRead
from app.services import gallery_service
from app.services.photo_storage import (
    PhotoStorage,
    PhotoStorageError,
    get_photo_storage,
)
from app.services.photo_validation import PhotoValidationError

router = APIRouter(prefix="/activities/{activity_id}/photos", tags=["Activity Photos"])
SessionDep = Annotated[Session, Depends(get_db)]
UserDep = Annotated[User, Depends(get_current_user)]
StorageDep = Annotated[PhotoStorage, Depends(get_photo_storage)]

GALLERY_DESCRIPTION = """
Authentication: access JWT required. Private S3-compatible storage; image bytes
and object keys are never returned by this API. Responses contain short-lived
presigned GET URLs (default 300 seconds, bounded by remaining gallery time).
CHECKED_IN/COMPLETED participants may view and upload strictly before end_at + 72h.
The organizer may view without participation, but organizer identity alone never
allows upload. At exactly end_at + 72h all gallery access closes.
Cancellation preserves existing photos and viewing, but blocks new uploads.
No automatic object/metadata cleanup is performed after expiry.
"""
ERRORS = {
    401: {"description": "Missing, expired or invalid access JWT."},
    403: {
        "description": "Caller is ineligible, gallery is closed, or caller is not the uploader for deletion."
    },
    404: {
        "description": "Activity/photo not found, including a photo belonging to another activity."
    },
    503: {"description": "Private object storage unavailable; retry later."},
}


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"


def _http_error(exc: Exception) -> HTTPException:
    return HTTPException(
        status_code=503 if isinstance(exc, PhotoStorageError) else exc.status_code,
        detail="Photo storage unavailable"
        if isinstance(exc, PhotoStorageError)
        else str(exc),
        headers={"Cache-Control": "private, no-store", "Vary": "Authorization"},
    )


@router.get(
    "",
    response_model=list[ActivityPhotoRead],
    summary="Read private activity gallery",
    description=GALLERY_DESCRIPTION + "\nPhotos are ordered by created_at ASC, id ASC.",
    responses=ERRORS,
)
def read(
    activity_id: UUID,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    response: Response,
) -> list[ActivityPhotoRead]:
    _private(response)
    try:
        return gallery_service.list_photos(session, activity_id, user.id, storage)
    except (gallery_service.GalleryError, PhotoStorageError) as exc:
        raise _http_error(exc) from exc


@router.post(
    "",
    response_model=ActivityPhotoRead,
    status_code=201,
    summary="Upload an activity photo",
    description=GALLERY_DESCRIPTION
    + """
Upload multipart/form-data with required field `file`. Maximum 10 MB (10,485,760
bytes), inclusive; only image/jpeg, image/png, image/webp. Actual image bytes must
decode and match the declared MIME; filename extensions are ignored. GIF/SVG
are forbidden. Maximum 3 photos per user per activity, enforced transactionally
under a PostgreSQL activity row lock. Failed DB writes attempt object cleanup.
""",
    responses={
        **ERRORS,
        409: {"description": "Maximum 3 photos reached."},
        413: {"description": "Photo exceeds 10 MB."},
        422: {"description": "Missing file, invalid/corrupt image or MIME mismatch."},
    },
)
def upload(
    activity_id: UUID,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    response: Response,
    file: Annotated[UploadFile, File(json_schema_extra={"format": "binary"})],
) -> ActivityPhotoRead:
    _private(response)
    try:
        return gallery_service.upload_photo(
            session, activity_id, user.id, file.file, file.content_type, storage
        )
    except (
        gallery_service.GalleryError,
        PhotoValidationError,
        PhotoStorageError,
    ) as exc:
        raise _http_error(exc) from exc


@router.delete(
    "/{photo_id}",
    status_code=204,
    summary="Delete your activity photo",
    description=GALLERY_DESCRIPTION
    + """
Only the uploader may delete, while they retain normal gallery view access.
Organizer identity grants no deletion of others' photos. Storage deletion happens
first; transient failure preserves DB metadata. A missing object is recoverable.
Cancellation allows own-photo deletion; closure blocks it. No moderation API.
""",
    responses=ERRORS,
)
def delete(
    activity_id: UUID,
    photo_id: UUID,
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    response: Response,
) -> None:
    _private(response)
    try:
        gallery_service.delete_photo(session, activity_id, photo_id, user.id, storage)
    except (gallery_service.GalleryError, PhotoStorageError) as exc:
        raise _http_error(exc) from exc
