from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import DEVELOPMENT_JWT_SECRET, Settings, get_settings
from app.main import create_app


@pytest.mark.parametrize("environment", ["development", "test"])
@pytest.mark.parametrize("secret", [DEVELOPMENT_JWT_SECRET, "test-secret"])
def test_development_and_test_accept_existing_secret_conventions(environment, secret):
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        environment=environment,
        jwt_secret=secret,
    )

    assert settings.jwt_secret == secret


@pytest.mark.parametrize("environment", ["development", "test"])
def test_development_and_test_keep_default_secret(environment, monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    settings = Settings(
        _env_file=None, database_url="sqlite://", environment=environment
    )

    assert settings.jwt_secret == DEVELOPMENT_JWT_SECRET


@pytest.mark.parametrize(
    "secret",
    [
        DEVELOPMENT_JWT_SECRET,
        "replace-me-with-a-long-random-secret",
        " change-me-in-development ",
        " replace-me-with-a-long-random-secret ",
        "short-production-test-secret",
        "",
        "   ",
    ],
)
def test_production_rejects_unsafe_secret_configuration(secret):
    with pytest.raises(ValidationError, match="jwt_secret") as error:
        Settings(
            _env_file=None,
            database_url="sqlite://",
            environment="production",
            jwt_secret=secret,
        )

    if secret.strip():
        assert secret not in str(error.value)


def test_production_rejects_missing_secret(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)

    with pytest.raises(ValidationError, match="production jwt_secret"):
        Settings(_env_file=None, database_url="sqlite://", environment="production")


@pytest.mark.parametrize("secret", ["p" * 31, " " + "p" * 31 + " "])
def test_production_secret_minimum_ignores_surrounding_whitespace(secret):
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            _env_file=None,
            database_url="sqlite://",
            environment="production",
            jwt_secret=secret,
        )


@pytest.mark.parametrize(
    "secret", ["p" * 32, "unit-test-production-signing-key-with-ample-length"]
)
def test_production_accepts_non_default_secret_at_or_above_minimum(secret):
    settings = Settings(
        _env_file=None,
        database_url="sqlite://",
        environment="production",
        jwt_secret=secret,
    )

    assert settings.jwt_secret == secret


def test_production_rejects_unsafe_secret_before_application_starts(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", DEVELOPMENT_JWT_SECRET)
    get_settings.cache_clear()

    try:
        with pytest.raises(ValidationError, match="production jwt_secret"):
            create_app()
    finally:
        get_settings.cache_clear()
