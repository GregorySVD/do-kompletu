from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token
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
        "identifier": "tester@example.com",
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
    assert second_response.json() == {"detail": "Email address is already registered"}


def test_register_duplicate_email_race_still_returns_conflict(client, monkeypatch):
    first_response = register_user(client)
    monkeypatch.setattr(
        "app.services.auth_service.get_user_by_email",
        lambda session, email: None,
    )

    second_response = register_user(client, display_name="Another User")

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Email address is already registered"}


@pytest.mark.parametrize(
    "duplicate_display_name",
    ["GregorySVD", "gregorysvd", "GREGORYSVD", "GrEgOrYsVd"],
)
def test_register_duplicate_display_name_returns_conflict(client, duplicate_display_name):
    first_response = register_user(
        client,
        email="first@example.com",
        display_name="GregorySVD",
    )
    second_response = register_user(
        client,
        email="second@example.com",
        display_name=duplicate_display_name,
    )

    assert first_response.status_code == 201
    assert first_response.json()["display_name"] == "GregorySVD"
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Username is already taken"}


def test_register_duplicate_display_name_race_returns_conflict(client, monkeypatch):
    first_response = register_user(
        client,
        email="first@example.com",
        display_name="GregorySVD",
    )
    monkeypatch.setattr(
        "app.services.auth_service.get_user_by_display_name",
        lambda session, display_name: None,
    )

    second_response = register_user(
        client,
        email="second@example.com",
        display_name="gregorysvd",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "Username is already taken"}


def test_database_enforces_case_insensitive_display_name_uniqueness(db_session):
    db_session.add(
        User(
            email="first@example.com",
            password_hash="not-a-real-password-hash",
            display_name="GregorySVD",
        )
    )
    db_session.commit()
    db_session.add(
        User(
            email="second@example.com",
            password_hash="not-a-real-password-hash",
            display_name="GREGORYSVD",
        )
    )

    with pytest.raises(IntegrityError, match="uq_users_display_name_lower"):
        db_session.commit()

    db_session.rollback()


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


@pytest.mark.parametrize(
    "identifier",
    ["Test User", "test user", "TEST USER", "TeSt UsEr"],
)
def test_login_accepts_case_insensitive_display_name(client, identifier):
    register_user(client)

    response = login_user(client, identifier=identifier)

    assert response.status_code == 200
    assert response.json()["access_token"]


@pytest.mark.parametrize(
    "identifier",
    ["  Test User  ", "  tester@example.com  ", "tester@EXAMPLE.COM"],
)
def test_login_normalizes_identifier_whitespace_and_email_domain(client, identifier):
    register_user(client)

    response = login_user(client, identifier=identifier)

    assert response.status_code == 200


def test_login_wrong_password_returns_unauthorized(client):
    register_user(client)

    response = login_user(client, password="WrongPass123")

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_unknown_user_returns_unauthorized(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "unknown@example.com", "password": "SecretPass123"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


def test_login_rejects_old_email_only_contract(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "tester@example.com", "password": "SecretPass123"},
    )

    assert response.status_code == 422


@pytest.mark.parametrize("username", ["tester@example.com", "test user", "TEST USER"])
def test_oauth2_token_accepts_email_or_display_name(client, username):
    register_user(client)

    response = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": "SecretPass123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert "refresh_token" not in body

    me_response = client.get(
        "/api/v1/users/me",
        headers=auth_header(body["access_token"]),
    )
    assert me_response.status_code == 200


@pytest.mark.parametrize("username", ["missing-user", "   "])
def test_oauth2_token_invalid_credentials_are_generic(client, username):
    response = client.post(
        "/api/v1/auth/token",
        data={"username": username, "password": "WrongPass123"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid credentials"}


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


@pytest.mark.parametrize("token_kind", ["malformed", "expired", "invalid-signature"])
def test_refresh_rejects_invalid_tokens_with_generic_unauthorized(client, token_kind):
    settings = get_settings()
    tokens = {
        "malformed": "not-a-real-token",
        "expired": create_refresh_token(uuid4(), expires_delta=timedelta(seconds=-10)),
        "invalid-signature": jwt.encode(
            {"sub": str(uuid4()), "type": "refresh"},
            "different-test-signing-secret",
            algorithm=settings.jwt_algorithm,
        ),
    }

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": tokens[token_kind]}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate refresh token"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "claims",
    [
        {"type": "refresh"},
        {"sub": 123, "type": "refresh"},
        {"sub": "invalid-user-uuid", "type": "refresh"},
        {"sub": str(uuid4()), "type": "unknown"},
        {"sub": str(uuid4()), "type": "refresh", "exp": "invalid-expiry"},
    ],
)
def test_refresh_rejects_invalid_authentication_claims(client, claims):
    settings = get_settings()
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)

    response = client.post("/api/v1/auth/refresh", json={"refresh_token": token})

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate refresh token"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("decode_error", [JWTError, JWTClaimsError, ExpiredSignatureError])
def test_refresh_handles_known_jwt_decode_exceptions(client, monkeypatch, decode_error):
    refresh_token = create_refresh_token(uuid4())

    def reject_token(*args, **kwargs):
        raise decode_error("Rejected by the JWT decoder")

    monkeypatch.setattr("app.core.security.jwt.decode", reject_token)

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate refresh token"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("claim_name", ["iat", "nbf", "exp"])
@pytest.mark.parametrize(
    "invalid_value", [None, [], {}, float("nan"), float("inf"), -float("inf")]
)
def test_refresh_rejects_invalid_numeric_date_claims(client, claim_name, invalid_value):
    settings = get_settings()
    refresh_token = jwt.encode(
        {"sub": str(uuid4()), "type": "refresh", claim_name: invalid_value},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate refresh token"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("value_kind", ["integer", "finite-float", "integer-string"])
def test_refresh_preserves_supported_numeric_date_values(client, value_kind):
    registration = register_user(client)
    settings = get_settings()
    now = int(datetime.now(UTC).timestamp())
    time_claims = {"iat": now - 10, "nbf": now - 10, "exp": now + 60}
    if value_kind == "finite-float":
        time_claims = {name: value + 0.5 for name, value in time_claims.items()}
    elif value_kind == "integer-string":
        time_claims = {name: str(value) for name, value in time_claims.items()}
    refresh_token = jwt.encode(
        {"sub": registration.json()["id"], "type": "refresh", **time_claims},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )

    response = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )

    assert response.status_code == 200
    assert response.json()["access_token"]


def test_refresh_does_not_mask_unexpected_jwt_decoder_failure(client, monkeypatch):
    refresh_token = create_refresh_token(uuid4())
    failure = TypeError("Unexpected decoder programming error")

    def broken_decoder(*args, **kwargs):
        raise failure

    monkeypatch.setattr("app.core.security.jwt.decode", broken_decoder)

    with pytest.raises(TypeError) as error:
        client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert error.value is failure


@pytest.mark.parametrize(
    "failure",
    [
        OperationalError("SELECT 1", {}, RuntimeError("Database unavailable")),
        RuntimeError("Unexpected service failure"),
    ],
)
def test_refresh_does_not_mask_database_or_service_failures(client, monkeypatch, failure):
    refresh_token = create_refresh_token(uuid4())

    def unavailable_user_lookup(*args, **kwargs):
        raise failure

    monkeypatch.setattr(
        "app.services.auth_service.get_user_by_id", unavailable_user_lookup
    )

    # This client propagates server exceptions; the original failure must escape
    # refresh's authentication handler instead of becoming a 401 response.
    with pytest.raises(type(failure)) as error:
        client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})

    assert error.value is failure


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


def test_patch_current_user_rejects_duplicate_display_name(client):
    register_user(
        client,
        email="first@example.com",
        display_name="GregorySVD",
    )
    register_user(
        client,
        email="second@example.com",
        display_name="Second User",
    )
    login_response = login_user(client, identifier="second@example.com")
    access_token = login_response.json()["access_token"]

    response = client.patch(
        "/api/v1/users/me",
        headers=auth_header(access_token),
        json={"display_name": "gregorysvd"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Username is already taken"}
