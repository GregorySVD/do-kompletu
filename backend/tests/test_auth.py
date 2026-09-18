from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.user import User


def register_user(client, **overrides):
    payload = {
        "email": "tester@example.com",
        "password": "SecretPass123",
        "display_name": "Test User",
    }
    payload.update(overrides)
    return client.post("/api/v1/auth/register", json=payload)


def login_user(client, **overrides):
    payload = {
        "email": "tester@example.com",
        "password": "SecretPass123",
    }
    payload.update(overrides)
    return client.post("/api/v1/auth/login", json=payload)


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_register_success(client):
    response = register_user(client)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "tester@example.com"
    assert body["display_name"] == "Test User"
    assert "password_hash" not in body


def test_register_duplicate_email_returns_conflict(client):
    first_response = register_user(client)
    second_response = register_user(client)

    assert first_response.status_code == 201
    assert second_response.status_code == 409


def test_password_is_stored_hashed(db_session, client):
    response = register_user(client, password="Plaintext123")

    stored_user = db_session.scalar(select(User).where(User.email == "tester@example.com"))

    assert response.status_code == 201
    assert stored_user is not None
    assert stored_user.password_hash != "Plaintext123"
    assert stored_user.password_hash.startswith("$argon2id$")


def test_login_success(client):
    register_user(client)

    response = login_user(client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]


def test_login_wrong_password_returns_unauthorized(client):
    register_user(client)

    response = login_user(client, password="WrongPass123")

    assert response.status_code == 401


def test_login_unknown_user_returns_unauthorized(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": "SecretPass123"},
    )

    assert response.status_code == 401


def test_get_current_user_requires_valid_access_token(client):
    register_user(client)
    login_response = login_user(client)
    access_token = login_response.json()["access_token"]

    response = client.get("/api/v1/users/me", headers=auth_header(access_token))

    assert response.status_code == 200
    assert response.json()["email"] == "tester@example.com"


def test_get_current_user_without_token_returns_unauthorized(client):
    response = client.get("/api/v1/users/me")

    assert response.status_code == 401


def test_get_current_user_with_invalid_access_token_returns_unauthorized(client):
    response = client.get("/api/v1/users/me", headers=auth_header("not-a-real-token"))

    assert response.status_code == 401


def test_get_current_user_with_expired_access_token_returns_unauthorized(client, db_session):
    register_user(client)
    user = db_session.scalar(select(User).where(User.email == "tester@example.com"))
    expired_token = create_access_token(user.id, expires_delta=timedelta(seconds=-1))

    response = client.get("/api/v1/users/me", headers=auth_header(expired_token))

    assert response.status_code == 401


def test_refresh_token_returns_new_access_token(client):
    register_user(client)
    login_response = login_user(client)
    refresh_token = login_response.json()["refresh_token"]

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 200
    refreshed_access_token = refresh_response.json()["access_token"]
    me_response = client.get("/api/v1/users/me", headers=auth_header(refreshed_access_token))
    assert me_response.status_code == 200


def test_refresh_token_cannot_be_used_as_access_token(client):
    register_user(client)
    login_response = login_user(client)
    refresh_token = login_response.json()["refresh_token"]

    response = client.get("/api/v1/users/me", headers=auth_header(refresh_token))

    assert response.status_code == 401


def test_access_token_cannot_be_used_as_refresh_token(client):
    register_user(client)
    login_response = login_user(client)
    access_token = login_response.json()["access_token"]

    response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": access_token},
    )

    assert response.status_code == 401


def test_patch_current_user_updates_allowed_profile_fields(client):
    register_user(client)
    login_response = login_user(client)
    access_token = login_response.json()["access_token"]

    response = client.patch(
        "/api/v1/users/me",
        headers=auth_header(access_token),
        json={"display_name": "Updated Name", "avatar_url": "https://example.com/avatar.png"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Name"
    assert response.json()["avatar_url"] == "https://example.com/avatar.png"
