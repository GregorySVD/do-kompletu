from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import get_settings

TokenType = Literal["access", "refresh"]

ARGON2_SALT_LENGTH = 16
ARGON2_HASH_LENGTH = 32
ARGON2_ITERATIONS = 3
ARGON2_LANES = 4
ARGON2_MEMORY_COST = 65536


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be validated."""


class ExpiredTokenError(InvalidTokenError):
    """Raised when a JWT is valid but expired."""


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password must not be empty")

    return Argon2id(
        salt=os.urandom(ARGON2_SALT_LENGTH),
        length=ARGON2_HASH_LENGTH,
        iterations=ARGON2_ITERATIONS,
        lanes=ARGON2_LANES,
        memory_cost=ARGON2_MEMORY_COST,
    ).derive_phc_encoded(password.encode("utf-8"))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        Argon2id.verify_phc_encoded(password.encode("utf-8"), password_hash)
    except (InvalidKey, TypeError, ValueError):
        return False
    return True


def _build_token(subject: UUID | str, token_type: TokenType, expires_delta: timedelta) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: UUID | str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    lifetime = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    return _build_token(subject=subject, token_type="access", expires_delta=lifetime)


def create_refresh_token(subject: UUID | str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    lifetime = expires_delta or timedelta(days=settings.refresh_token_expire_days)
    return _build_token(subject=subject, token_type="refresh", expires_delta=lifetime)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise ExpiredTokenError("Token has expired") from exc
    except JWTError as exc:
        raise InvalidTokenError("Token is invalid") from exc

    subject = payload.get("sub")
    token_type = payload.get("type")

    if not subject or token_type != expected_type:
        raise InvalidTokenError("Token has an invalid payload")

    return payload
