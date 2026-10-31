"""Narrow private-object interface. No bucket creation or I/O at API startup."""

from functools import cached_property, lru_cache
from typing import Protocol

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import Settings, get_settings


class PhotoStorageError(Exception):
    """Storage unavailable; never expose SDK messages/credentials to clients."""


class PhotoStorage(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def delete(self, key: str) -> None: ...

    def presigned_get_url(self, key: str, ttl_seconds: int) -> str: ...


class S3PhotoStorage:
    def __init__(self, settings: Settings):
        self.settings = settings

    @cached_property
    def client(self):
        settings = self.settings
        if not (
            settings.s3_bucket
            and settings.s3_access_key_id
            and settings.s3_secret_access_key
        ):
            raise PhotoStorageError("Photo storage is not configured")
        return boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id.get_secret_value(),
            aws_secret_access_key=settings.s3_secret_access_key.get_secret_value(),
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                connect_timeout=3,
                read_timeout=10,
                retries={"mode": "standard", "total_max_attempts": 2},
            ),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self.client.put_object(
                Bucket=self.settings.s3_bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                CacheControl="private, no-store",
            )
        except (BotoCoreError, ClientError) as exc:
            raise PhotoStorageError("Photo storage upload failed") from exc

    def delete(self, key: str) -> None:
        try:
            # S3 DeleteObject is idempotent for an already-missing key.
            self.client.delete_object(Bucket=self.settings.s3_bucket, Key=key)
        except (BotoCoreError, ClientError) as exc:
            raise PhotoStorageError("Photo storage deletion failed") from exc

    def presigned_get_url(self, key: str, ttl_seconds: int) -> str:
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.settings.s3_bucket, "Key": key},
                ExpiresIn=ttl_seconds,
            )
        except (BotoCoreError, ClientError) as exc:
            raise PhotoStorageError("Photo URL generation failed") from exc


@lru_cache
def get_photo_storage() -> PhotoStorage:
    return S3PhotoStorage(get_settings())
