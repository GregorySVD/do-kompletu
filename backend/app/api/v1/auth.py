from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.auth import (
    AccessTokenResponse,
    RefreshTokenRequest,
    TokenPair,
    UserLogin,
    UserRegister,
)
from app.schemas.user import UserRead
from app.services.auth_service import (
    DuplicateEmailError,
    InvalidCredentialsError,
    authenticate_user,
    issue_token_pair,
    refresh_access_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegister,
    session: Annotated[Session, Depends(get_db)],
) -> UserRead:
    try:
        user = register_user(session, payload)
    except DuplicateEmailError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email address is already registered",
        ) from exc
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenPair)
def login(
    payload: UserLogin,
    session: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    try:
        user = authenticate_user(session, payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return issue_token_pair(user)


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    payload: RefreshTokenRequest,
    session: Annotated[Session, Depends(get_db)],
) -> AccessTokenResponse:
    try:
        return refresh_access_token(session, payload.refresh_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate refresh token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
