from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.security import verify_password
from app.models.user import User
from app.schemas.auth import UserRegister
from app.scripts.create_bootstrap_user import (
    BootstrapUserConflictError,
    ensure_bootstrap_user,
)


def bootstrap_payload(password: str = "BootstrapPass123") -> UserRegister:
    return UserRegister(
        email="bootstrap@example.com",
        display_name="BootstrapUser",
        password=password,
    )


def test_bootstrap_user_is_created_with_hashed_password(db_session):
    user, created = ensure_bootstrap_user(db_session, bootstrap_payload())

    assert created is True
    assert user.password_hash != "BootstrapPass123"
    assert user.password_hash.startswith("$argon2id$")
    assert verify_password("BootstrapPass123", user.password_hash)


def test_bootstrap_user_is_idempotent_and_does_not_replace_password(db_session):
    first_user, first_created = ensure_bootstrap_user(db_session, bootstrap_payload())
    original_password_hash = first_user.password_hash

    second_user, second_created = ensure_bootstrap_user(
        db_session,
        bootstrap_payload(password="DifferentPass123"),
    )

    assert first_created is True
    assert second_created is False
    assert second_user.id == first_user.id
    assert second_user.password_hash == original_password_hash
    assert verify_password("BootstrapPass123", second_user.password_hash)
    assert not verify_password("DifferentPass123", second_user.password_hash)
    assert db_session.scalar(select(func.count()).select_from(User)) == 1


def test_bootstrap_user_refuses_identifier_collision(db_session):
    ensure_bootstrap_user(db_session, bootstrap_payload())

    with pytest.raises(BootstrapUserConflictError):
        ensure_bootstrap_user(
            db_session,
            UserRegister(
                email="different@example.com",
                display_name="BootstrapUser",
                password="DifferentPass123",
            ),
        )
