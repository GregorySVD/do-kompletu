from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings

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
        "description": "Authenticated current-user profile operations.",
    },
    {
        "name": "Activities",
        "description": "Create activities and browse public activity data.",
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
