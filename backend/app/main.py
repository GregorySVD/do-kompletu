from copy import deepcopy
from math import isfinite
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute, iter_route_contexts
from sqlalchemy import text
from sqlalchemy.exc import DisconnectionError, InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as DatabaseTimeoutError
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.core.config import get_settings
from app.db.session import get_db
from app.workers.participation_lifecycle import lifecycle_lifespan

OPENAPI_TAGS = [
    {
        "name": "Administration",
        "description": "Minimal moderation. Active administrator authentication required; uses a simple is_admin boolean, not a general role system.",
    },
    {
        "name": "Activity Photos",
        "description": "Private activity galleries for checked-in/completed participants; organizers have view-only access. Normal access closes at end_at + 72h. Active admins can delete by photo/activity UUID even after closure; admin status does not grant browsing.",
    },
    {
        "name": "Authentication",
        "description": (
            "Register accounts and obtain JWTs. Frontend clients normally use the "
            "JSON `POST /api/v1/auth/login` endpoint, which returns access and refresh "
            "tokens. Swagger's **Authorize** dialog uses form-encoded "
            "`POST /api/v1/auth/token`, which returns an access token only. In that "
            "dialog, **username accepts either email or display name**, display-name "
            "comparison is case-insensitive, the password is case-sensitive, and "
            "`client_id` and `client_secret` should be left blank."
        ),
    },
    {
        "name": "Users",
        "description": "Authenticated current-user profile and organized/joined/waitlisted activity lists.",
    },
    {
        "name": "Activities",
        "description": (
            "Create, edit, cancel, finalize attendance, and browse activities; join, leave, confirm, or check in with an access JWT. "
            "Detail authentication is optional for caller-specific membership."
        ),
    },
    {
        "name": "Reference Data",
        "description": "Canonical values accepted by API request schemas.",
    },
    {
        "name": "Health",
        "description": "Service availability checks.",
    },
]


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        lifespan=lifecycle_lifespan(settings),
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Backend API for creating and discovering real-world activities. "
            "Frontend clients can use JSON `POST /api/v1/auth/login` for an access/"
            "refresh pair. For Swagger, select **Authorize** and enter either an "
            "email or display name in `username`, enter the case-sensitive password, "
            "and leave `client_id` and `client_secret` blank."
        ),
        openapi_tags=OPENAPI_TAGS,
    )

    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(api_router)

    @app.exception_handler(RequestValidationError)
    async def validation_error_response(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # JSON parsing can produce nonfinite floats, including valid JSON 1e999.
        # Keep the standard validation body serializable when it echoes input.
        errors = jsonable_encoder(
            exc.errors(),
            custom_encoder={float: lambda value: value if isfinite(value) else str(value)},
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": errors},
        )

    default_openapi = app.openapi

    def openapi_with_examples() -> dict:
        if app.openapi_schema is None:
            schema = default_openapi()
            # FastAPI removes None recursively, even inside request/response examples.
            # Restore explicit examples so nullable fields match actual responses.
            for route in iter_route_contexts(app.routes):
                if (
                    not isinstance(route.original_route, APIRoute)
                    or not route.include_in_schema
                ):
                    continue
                for method in route.methods:
                    operation = schema["paths"][route.path_format][method.lower()]
                    if route.body_field is not None:
                        body_info = route.body_field.field_info
                        if body_info.openapi_examples:
                            operation["requestBody"]["content"][body_info.media_type][
                                "examples"
                            ] = deepcopy(body_info.openapi_examples)
                    for code, response in route.responses.items():
                        for media_type, media in response.get("content", {}).items():
                            target = operation["responses"][str(code)]["content"][
                                media_type
                            ]
                            for key in ("example", "examples"):
                                if key in media:
                                    target[key] = deepcopy(media[key])
            app.openapi_schema = schema
        return app.openapi_schema

    app.openapi = openapi_with_examples

    @app.get(
        "/health",
        tags=["Health"],
        summary="Check service health",
        description="Return a lightweight response when the API process is available.",
        response_description="The API process is healthy.",
    )
    async def health_check() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(
        "/ready",
        tags=["Health"],
        summary="Check database readiness",
        description=(
            "Execute SELECT 1 using the configured database session. Returns 503 "
            "when the database connection is unavailable; does not inspect schema "
            "or PostGIS. Use /health for lightweight process liveness."
        ),
        responses={
            200: {
                "description": "The API can reach its database.",
                "content": {"application/json": {"example": {"status": "ok"}}},
            },
            503: {
                "description": "The database connection is unavailable.",
                "content": {
                    "application/json": {"example": {"detail": "Database unavailable"}}
                },
            },
        },
    )
    def readiness_check(session: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
        try:
            session.execute(text("SELECT 1"))
        except (
            OperationalError,
            InterfaceError,
            DisconnectionError,
            DatabaseTimeoutError,
        ) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            ) from exc
        return {"status": "ok"}

    return app


app = create_app()
