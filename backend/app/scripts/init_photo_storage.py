"""Explicit local bucket provisioning; never coupled to API/worker startup."""

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.services.photo_storage import S3PhotoStorage


def main() -> None:
    settings = get_settings()
    if settings.environment == "production":
        raise RuntimeError("Provision production buckets through deployment tooling")
    storage = S3PhotoStorage(settings)
    client = storage.client
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"404", "NoSuchBucket", "NotFound"}:
            raise RuntimeError("Unable to inspect local photo bucket") from None
        args = {"Bucket": settings.s3_bucket}
        if settings.s3_region != "us-east-1":
            args["CreateBucketConfiguration"] = {
                "LocationConstraint": settings.s3_region
            }
        try:
            client.create_bucket(**args)  # Default private, no public policy/ACL.
        except ClientError as create_error:
            if create_error.response["Error"]["Code"] != "BucketAlreadyOwnedByYou":
                raise RuntimeError("Unable to create local photo bucket") from None
        client.head_bucket(Bucket=settings.s3_bucket)
    print("Local photo bucket is ready (no public policy or ACL was added).")


if __name__ == "__main__":
    main()
