from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
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
from app.models.user import (
    DISPLAY_NAME_UNIQUE_INDEX,
    EMAIL_UNIQUE_CONSTRAINT,
    User,
)
from app.schemas.auth import AccessTokenResponse, TokenPair, UserLogin, UserRegister
from app.schemas.user import UserUpdate


class DuplicateEmailError(Exception):
    """Raised when a registration attempts to reuse an email address."""


class DuplicateUsernameError(Exception):
    """Raised when a display name is already used by another user."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials are invalid."""


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email))


def get_user_by_id(session: Session, user_id: UUID) -> User | None:
    return session.get(User, user_id)


def get_user_by_display_name(session: Session, display_name: str) -> User | None:
    return session.scalar(
        select(User).where(func.lower(User.display_name) == func.lower(display_name))
    )


def register_user(session: Session, payload: UserRegister) -> User:
    existing_user = get_user_by_email(session, payload.email)
    if existing_user is not None:
        raise DuplicateEmailError("Email address is already registered")

    existing_user = get_user_by_display_name(session, payload.display_name)
    if existing_user is not None:
        raise DuplicateUsernameError("Username is already taken")

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
        if _is_duplicate_username_error(exc):
            raise DuplicateUsernameError("Username is already taken") from exc
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
    if payload.display_name is not None:
        existing_user = get_user_by_display_name(session, payload.display_name)
        if existing_user is not None and existing_user.id != user.id:
            raise DuplicateUsernameError("Username is already taken")

    for field_name, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field_name, value)

    session.add(user)

    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if _is_duplicate_username_error(exc):
            raise DuplicateUsernameError("Username is already taken") from exc
        raise

    session.refresh(user)
    return user


def _is_duplicate_email_error(error: IntegrityError) -> bool:
    constraint_name = _constraint_name(error)
    if constraint_name is not None:
        return constraint_name == EMAIL_UNIQUE_CONSTRAINT

    message = str(error.orig).lower()
    return (
        EMAIL_UNIQUE_CONSTRAINT in message
        or "unique constraint failed: users.email" in message
    )


def _is_duplicate_username_error(error: IntegrityError) -> bool:
    constraint_name = _constraint_name(error)
    if constraint_name is not None:
        return constraint_name == DISPLAY_NAME_UNIQUE_INDEX

    return DISPLAY_NAME_UNIQUE_INDEX in str(error.orig).lower()


def _constraint_name(error: IntegrityError) -> str | None:
    diagnostic = getattr(error.orig, "diag", None)
    return getattr(diagnostic, "constraint_name", None)
