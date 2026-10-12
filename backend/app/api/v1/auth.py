from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError
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
    DuplicateUsernameError,
    InvalidCredentialsError,
    authenticate_user,
    issue_access_token,
    issue_token_pair,
    refresh_access_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

UNAUTHORIZED_RESPONSE = {
    "description": "The identifier/password pair or supplied token is invalid.",
    "content": {
        "application/json": {"example": {"detail": "Invalid credentials"}}
    },
}
TOKEN_PAIR_EXAMPLE = {
    "access_token": "<access-token>",
    "refresh_token": "<refresh-token>",
    "token_type": "bearer",
}
ACCESS_TOKEN_EXAMPLE = {
    "access_token": "<access-token>",
    "token_type": "bearer",
}


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
    description=(
        "Create an account with a unique email and case-insensitively unique "
        "display name. Submitted display-name capitalization is preserved."
    ),
    response_description="The newly registered public user profile.",
    responses={
        409: {
            "description": "The email or display name is already registered.",
            "content": {
                "application/json": {
                    "examples": {
                        "email": {
                            "value": {"detail": "Email address is already registered"}
                        },
                        "username": {
                            "value": {"detail": "Username is already taken"}
                        },
                    }
                }
            },
        },
        422: {"description": "The registration payload is invalid."},
    },
)
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
    except DuplicateUsernameError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username is already taken",
        ) from exc
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenPair,
    summary="Log in with JSON",
    description=(
        "Frontend-oriented login accepting an `application/json` body. `identifier` "
        "may be an email address or display name; display-name matching is "
        "case-insensitive, while the password is case-sensitive. On success this "
        "endpoint returns both access and refresh JWTs. Swagger's Authorize dialog "
        "uses the separate form-encoded `POST /api/v1/auth/token` endpoint."
    ),
    response_description="A bearer access/refresh token pair.",
    responses={
        200: {
            "description": "Authentication succeeded.",
            "content": {"application/json": {"example": TOKEN_PAIR_EXAMPLE}},
        },
        401: UNAUTHORIZED_RESPONSE,
        422: {"description": "The JSON login payload is invalid."},
    },
)
def login(
    payload: UserLogin,
    session: Annotated[Session, Depends(get_db)],
) -> TokenPair:
    try:
        user = authenticate_user(session, payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return issue_token_pair(user)


@router.post(
    "/token",
    response_model=AccessTokenResponse,
    summary="Obtain a Swagger-compatible access token",
    description="""
OAuth2 password-flow endpoint used by Swagger's **Authorize** dialog. This endpoint
accepts `application/x-www-form-urlencoded` data, not the JSON login body.

- Enter either the account **email or display name** in `username`.
- Display-name comparison is **case-insensitive**.
- Enter the account's **case-sensitive** password in `password`.
- Leave `client_id` and `client_secret` **blank**.

Example form values:

```text
username=kacper
password=StrongPassword123
client_id=
client_secret=
```

The same account can instead use `username=kacper@example.com` with its exact
password.

The response contains an access token only. Use `POST /api/v1/auth/login` when a
frontend client needs both access and refresh tokens.
""",
    response_description="A bearer access token compatible with Swagger authorization.",
    responses={
        200: {
            "description": "Authentication succeeded.",
            "content": {"application/json": {"example": ACCESS_TOKEN_EXAMPLE}},
        },
        401: UNAUTHORIZED_RESPONSE,
        422: {"description": "Required form fields are missing or invalid."},
    },
)
def token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: Annotated[Session, Depends(get_db)],
) -> AccessTokenResponse:
    try:
        payload = UserLogin(identifier=form_data.username, password=form_data.password)
        user = authenticate_user(session, payload)
    except (InvalidCredentialsError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return issue_access_token(user)


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Refresh an access token",
    description=(
        "Exchange a valid refresh JWT from the JSON login endpoint for a new "
        "short-lived access JWT. Access tokens cannot be used here."
    ),
    response_description="A newly issued bearer access token.",
    responses={
        200: {
            "description": "The refresh token was accepted.",
            "content": {"application/json": {"example": ACCESS_TOKEN_EXAMPLE}},
        },
        401: {
            "description": "The refresh token is invalid, expired, or unavailable.",
            "content": {
                "application/json": {
                    "example": {"detail": "Could not validate refresh token"}
                }
            },
        },
        422: {"description": "The refresh request payload is invalid."},
    },
)
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
