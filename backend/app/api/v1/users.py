from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate
from app.services.auth_service import DuplicateUsernameError, update_user_profile

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get the current user",
    description="Return the public profile associated with the access bearer token.",
    response_description="The authenticated user's public profile.",
    responses={
        401: {
            "description": "The access token is missing, invalid, or expired.",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not validate credentials"}
                }
            },
        }
    },
)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserRead,
    summary="Update the current user's profile",
    description=(
        "Update the authenticated user's display name and/or avatar. Display names "
        "remain unique case-insensitively."
    ),
    response_description="The updated public user profile.",
    responses={
        401: {"description": "A valid access bearer token is required."},
        409: {
            "description": "The requested display name is already used.",
            "content": {
                "application/json": {
                    "example": {"detail": "Username is already taken"}
                }
            },
        },
        422: {"description": "The profile update payload is invalid."},
    },
)
def patch_current_user(
    payload: UserUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_db)],
) -> UserRead:
    try:
        updated_user = update_user_profile(session, current_user, payload)
    except DuplicateUsernameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken",
        ) from exc
    return UserRead.model_validate(updated_user)
