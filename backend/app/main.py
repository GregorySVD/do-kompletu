from copy import deepcopy

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute, iter_route_contexts

from app.api.router import api_router
from app.core.config import get_settings
from app.workers.participation_lifecycle import lifecycle_lifespan

OPENAPI_TAGS = [
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

    return app


app = create_app()
