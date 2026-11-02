from urllib.parse import parse_qs, urlparse

import pytest
from botocore.stub import Stubber
from pydantic import ValidationError

from app.core.config import Settings
from app.services.photo_storage import PhotoStorageError, S3PhotoStorage


def settings(**changes):
    return Settings(
        _env_file=None,
        database_url="sqlite://",
        environment="test",
        s3_endpoint_url="http://127.0.0.1:9000",
        s3_bucket="private-photos",
        s3_access_key_id="test-access",
        s3_secret_access_key="photo-s3-secret",
        **changes,
    )


def test_s3_adapter_private_put_idempotent_delete_and_presigning_without_network():
    storage = S3PhotoStorage(settings())
    with Stubber(storage.client) as stub:
        stub.add_response(
            "put_object",
            {},
            {
                "Bucket": "private-photos",
                "Key": "x.jpg",
                "Body": b"data",
                "ContentType": "image/jpeg",
                "CacheControl": "private, no-store",
            },
        )  # No public-read ACL.
        stub.add_response(
            "delete_object", {}, {"Bucket": "private-photos", "Key": "x.jpg"}
        )
        storage.put("x.jpg", b"data", "image/jpeg")
        storage.delete("x.jpg")
        url = urlparse(storage.presigned_get_url("x.jpg", 100))
        assert url.path == "/private-photos/x.jpg"
        assert parse_qs(url.query)["X-Amz-Expires"] == ["100"]
        assert parse_qs(url.query)["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
        stub.assert_no_pending_responses()
    assert "photo-s3-secret" not in repr(storage.settings)
    assert "test-access" not in repr(storage.settings)


@pytest.mark.parametrize("operation", ["put_object", "delete_object"])
def test_sdk_errors_translated_to_storage_error(operation):
    storage = S3PhotoStorage(settings())
    with Stubber(storage.client) as stub:
        stub.add_client_error(
            operation, service_error_code="SlowDown", http_status_code=503
        )
        with pytest.raises(PhotoStorageError):
            if operation == "put_object":
                storage.put("x", b"data", "image/png")
            else:
                storage.delete("x")


def test_unconfigured_storage_has_no_network_or_startup_dependency():
    storage = S3PhotoStorage(
        Settings(_env_file=None, database_url="sqlite://", environment="test")
    )
    with pytest.raises(PhotoStorageError, match="not configured"):
        storage.put("x", b"data", "image/png")


@pytest.mark.parametrize("ttl", [0, -1, 901])
def test_presigned_ttl_must_be_positive_and_short(ttl):
    with pytest.raises(ValidationError):
        settings(s3_presigned_url_ttl_seconds=ttl)
