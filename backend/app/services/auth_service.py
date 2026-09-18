from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    InvalidTokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, TokenPair, UserLogin, UserRegister
from app.schemas.user import UserUpdate


class DuplicateEmailError(Exception):
    """Raised when a registration attempts to reuse an email address."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid."""


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))


def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    return session.get(User, user_id)


def register_user(session: Session, payload: UserRegister) -> User:
    existing_user = get_user_by_email(session, payload.email)
    if existing_user is not None:
        raise DuplicateEmailError("Email address is already registered")

    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
    )
    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_duplicate_email_error(exc):
            raise DuplicateEmailError("Email address is already registered") from exc
        raise

    session.refresh(user)
    return user


def authenticate_user(session: Session, payload: UserLogin) -> User:
    user = get_user_by_email(session, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise InvalidCredentialsError("Invalid email or password")
    if not user.is_active:
        raise InvalidCredentialsError("Invalid email or password")
    return user


def issue_token_pair(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


def resolve_user_from_token(session: Session, token: str, expected_type: str) -> User:
    payload = decode_token(token, expected_type=expected_type)

    try:
        user_id = UUID(str(payload["sub"]))
    except ValueError as exc:
        raise InvalidTokenError("Token subject is invalid") from exc

    user = get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise InvalidTokenError("User is not available")
    return user


def refresh_access_token(session: Session, refresh_token: str) -> AccessTokenResponse:
    user = resolve_user_from_token(session, refresh_token, expected_type="refresh")
    return AccessTokenResponse(access_token=create_access_token(user.id))


def update_user_profile(session: Session, user: User, payload: UserUpdate) -> User:
    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field_name, value)

    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def _is_duplicate_email_error(error: IntegrityError) -> bool:
    message = str(error).lower()
    return "uq_users_email" in message or "users.email" in message or "unique constraint" in message
