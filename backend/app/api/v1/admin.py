from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import AdminActivityRead, AdminUserActiveUpdate, AdminUserRead
from app.services import admin_service
from app.services.activity_management_service import (
    ActivityManagementError,
    cancel_activity,
)


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "Authorization"


router = APIRouter(
    prefix="/admin",
    tags=["Administration"],
    dependencies=[Depends(_private)],
    responses={
        401: {"description": "Active account with a valid access JWT required."},
        403: {"description": "Administrator authentication required."},
    },
)
AdminDep = Annotated[User, Depends(require_admin)]
SessionDep = Annotated[Session, Depends(get_db)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get(
    "/users",
    response_model=list[AdminUserRead],
    summary="List users for moderation",
    description="Administrator authentication required. Ordered by created_at ASC, id ASC. Includes inactive accounts and email; excludes authentication secrets.",
)
def users(
    admin: AdminDep,
    session: SessionDep,
    limit: Limit = 20,
    offset: Offset = 0,
) -> list[AdminUserRead]:
    return admin_service.list_users(session, limit=limit, offset=offset)


@router.patch(
    "/users/{user_id}/active",
    response_model=AdminUserRead,
    summary="Activate or deactivate another user",
    description="Administrator authentication required. Deactivation rejects subsequent login, protected access and refresh requests. Self-deactivation is forbidden. Repeating the requested state succeeds.",
    responses={
        404: {"description": "User not found."},
        409: {"description": "Administrators cannot deactivate themselves."},
        422: {
            "description": "Invalid UUID or body; only boolean is_active is accepted."
        },
    },
)
def active(
    user_id: UUID,
    payload: AdminUserActiveUpdate,
    admin: AdminDep,
    session: SessionDep,
) -> AdminUserRead:
    try:
        return AdminUserRead.model_validate(
            admin_service.set_user_active(
                session, user_id, admin.id, is_active=payload.is_active
            )
        )
    except admin_service.AdministrationError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get(
    "/activities",
    response_model=list[AdminActivityRead],
    summary="List activities for moderation",
    description="Administrator authentication required. Includes ended and cancelled activities. Ordered by created_at ASC, id ASC. No private participant data or caller-specific permissions.",
)
def activities(
    admin: AdminDep,
    session: SessionDep,
    limit: Limit = 20,
    offset: Offset = 0,
) -> list[AdminActivityRead]:
    return admin_service.list_activities(session, limit=limit, offset=offset)


@router.post(
    "/activities/{activity_id}/cancel",
    response_model=AdminActivityRead,
    summary="Cancel an activity as administrator",
    description="Administrator authentication required. Uses organizer cancellation rules and locking; ownership is not required. Preserves participation, check-in and gallery history. Repeated cancellation and ended activities return 409.",
    responses={
        404: {"description": "Activity not found."},
        409: {"description": "Activity is already cancelled or has ended."},
        422: {"description": "Invalid activity UUID."},
    },
)
def cancel(
    activity_id: UUID, admin: AdminDep, session: SessionDep
) -> AdminActivityRead:
    try:
        return admin_service.activity_to_admin_read(
            cancel_activity(session, activity_id, admin.id, is_admin=admin.is_admin)
        )
    except ActivityManagementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
