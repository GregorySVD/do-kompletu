"""Opt-in local S3 smoke test; default tests use FakeStorage/Stubber only."""

import os
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import ProxyHandler, build_opener
from uuid import uuid4

import pytest
from gallery_data import NOW, image_bytes, seed

from app.core.config import Settings
from app.core.security import create_access_token
from app.main import app
from app.services import gallery_service
from app.services.photo_storage import S3PhotoStorage, get_photo_storage

pytestmark = pytest.mark.skipif(
    not os.getenv("MINIO_TEST_ENDPOINT_URL"),
    reason="MINIO_TEST_ENDPOINT_URL is not configured (optional local storage smoke test)",
)


def test_private_bucket_api_upload_signed_get_and_delete(
    client, db_session, monkeypatch
):
    bucket = "dk-gallery-smoke-" + uuid4().hex
    storage = S3PhotoStorage(
        Settings(
            _env_file=None,
            database_url="sqlite://",
            environment="test",
            s3_endpoint_url=os.environ["MINIO_TEST_ENDPOINT_URL"],
            s3_region="us-east-1",
            s3_bucket=bucket,
            s3_access_key_id=os.environ["MINIO_TEST_ACCESS_KEY_ID"],
            s3_secret_access_key=os.environ["MINIO_TEST_SECRET_ACCESS_KEY"],
        )
    )
    storage.client.create_bucket(Bucket=bucket)
    try:
        activity, users = seed(db_session)
        monkeypatch.setattr(gallery_service, "utc_now", lambda: NOW)
        app.dependency_overrides[get_photo_storage] = lambda: storage
        headers = {"Authorization": f"Bearer {create_access_token(users[1].id)}"}
        path = f"/api/v1/activities/{activity.id}/photos"
        data = image_bytes("PNG")
        response = client.post(
            path, headers=headers, files={"file": ("x.png", data, "image/png")}
        )
        assert response.status_code == 201
        photo = response.json()
        opener = build_opener(ProxyHandler({}))
        with opener.open(photo["url"], timeout=5) as download:
            assert download.read() == data
            assert download.headers["Content-Type"] == "image/png"
            assert download.headers["Cache-Control"] == "private, no-store"
        parsed = urlsplit(photo["url"])
        unsigned = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
        with pytest.raises(HTTPError) as denied:
            opener.open(unsigned, timeout=5)
        assert denied.value.code == 403
        assert client.get(path, headers=headers).json()[0]["id"] == photo["id"]
        assert (
            client.delete(path + f"/{photo['id']}", headers=headers).status_code == 204
        )
        assert client.get(path, headers=headers).json() == []
        assert storage.client.list_objects_v2(Bucket=bucket).get("KeyCount") == 0
    finally:
        for item in storage.client.list_objects_v2(Bucket=bucket).get("Contents", []):
            storage.delete(item["Key"])
        storage.client.delete_bucket(Bucket=bucket)
