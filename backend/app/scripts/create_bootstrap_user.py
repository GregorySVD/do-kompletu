from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_session_factory
from app.models.user import User
from app.schemas.auth import UserRegister
from app.services.auth_service import (
    get_user_by_display_name,
    get_user_by_email,
    register_user,
)


class BootstrapUserConflictError(Exception):
    """Raised when bootstrap identifiers belong to another existing account."""


def ensure_bootstrap_user(
    session: Session,
    payload: UserRegister,
) -> tuple[User, bool]:
    user_by_email = get_user_by_email(session, payload.email)
    user_by_name = get_user_by_display_name(session, payload.display_name)

    if user_by_email is None and user_by_name is None:
        return register_user(session, payload), True

    if (
        user_by_email is not None
        and user_by_name is not None
        and user_by_email.id != user_by_name.id
    ):
        raise BootstrapUserConflictError(
            "Bootstrap email and display name belong to different existing users"
        )

    existing_user = user_by_email or user_by_name
    if existing_user is None:
        raise RuntimeError("Existing bootstrap user could not be resolved")
    if (
        existing_user.email != payload.email
        or existing_user.display_name.lower() != payload.display_name.lower()
    ):
        raise BootstrapUserConflictError(
            "Bootstrap email or display name is already used by another account"
        )

    return existing_user, False


def _bootstrap_payload(settings: Settings) -> UserRegister:
    configured_values = {
        "BOOTSTRAP_USER_EMAIL": settings.bootstrap_user_email,
        "BOOTSTRAP_USER_DISPLAY_NAME": settings.bootstrap_user_display_name,
        "BOOTSTRAP_USER_PASSWORD": settings.bootstrap_user_password,
    }
    missing_values = [
        name for name, value in configured_values.items() if not value or not value.strip()
    ]
    if missing_values:
        names = ", ".join(missing_values)
        raise SystemExit(f"Missing bootstrap user settings: {names}")

    return UserRegister(
        email=settings.bootstrap_user_email,
        display_name=settings.bootstrap_user_display_name,
        password=settings.bootstrap_user_password,
    )


def main() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise SystemExit("Bootstrap user creation is disabled in production")

    payload = _bootstrap_payload(settings)
    with get_session_factory()() as session:
        try:
            user, created = ensure_bootstrap_user(session, payload)
        except BootstrapUserConflictError as exc:
            raise SystemExit(str(exc)) from exc

    action = "created" if created else "already exists; credentials were not changed"
    print(f"Bootstrap user {user.email} ({user.display_name}) {action}.")


if __name__ == "__main__":
    main()
