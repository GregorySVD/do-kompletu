from datetime import timedelta
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from gallery_data import END, NOW, FakeStorage, image_bytes, seed, set_status
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import create_access_token, create_refresh_token
from app.main import app
from app.models.activity_participation import ParticipationStatus
from app.models.activity_photo import ActivityPhoto
from app.services import activity_service, gallery_service
from app.services.photo_storage import get_photo_storage
from app.services.photo_validation import (
    MAX_PHOTO_BYTES,
    PhotoValidationError,
    read_bounded,
)


def test_image_decompression_bomb_is_rejected(monkeypatch):
    from PIL import Image

    from app.services.photo_validation import validate_photo

    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 40)
    with pytest.raises(PhotoValidationError, match="Invalid or unsafe image"):
        validate_photo(BytesIO(image_bytes("PNG")), "image/png")


@pytest.fixture
def gallery(client, db_session, monkeypatch):
    activity, users = seed(db_session)
    storage = FakeStorage()
    app.dependency_overrides[get_photo_storage] = lambda: storage
    clock = [NOW]
    monkeypatch.setattr(gallery_service, "utc_now", lambda: clock[0])
    headers = [{"Authorization": f"Bearer {create_access_token(u.id)}"} for u in users]
    return activity, users, storage, clock, headers


def path(gallery):
    return f"/api/v1/activities/{gallery[0].id}/photos"


def post(
    client, gallery, user=1, data=None, mime="image/jpeg", filename="../../evil.svg"
):
    return client.post(
        path(gallery),
        headers=gallery[4][user],
        files={"file": (filename, image_bytes() if data is None else data, mime)},
    )


def count(session):
    return session.scalar(select(func.count()).select_from(ActivityPhoto))


def permissions(gallery, session, user=1):
    result = activity_service.get_activity_by_id(
        session,
        gallery[0].id,
        current_user_id=gallery[1][user].id,
        as_of=gallery[3][0],
    )
    return activity_service.activity_to_read(result).permissions


@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_gallery_anonymous_requires_auth(client, gallery, method):
    url = path(gallery) + (f"/{uuid4()}" if method == "delete" else "")
    kwargs = (
        {"files": {"file": ("photo.jpg", image_bytes(), "image/jpeg")}}
        if method == "post"
        else {}
    )
    assert getattr(client, method)(url, **kwargs).status_code == 401


def test_gallery_refresh_token_is_not_access_token(client, gallery):
    headers = {"Authorization": f"Bearer {create_refresh_token(gallery[1][1].id)}"}
    assert client.get(path(gallery), headers=headers).status_code == 401


@pytest.mark.parametrize("status", list(ParticipationStatus))
def test_status_permissions_and_endpoints_agree(client, gallery, db_session, status):
    set_status(db_session, gallery[0].id, gallery[1][1].id, status)
    db_session.commit()
    allowed = status in {"CHECKED_IN", "COMPLETED"}
    p = permissions(gallery, db_session)
    assert p.can_view_gallery == p.can_upload_photo == allowed
    assert client.get(path(gallery), headers=gallery[4][1]).status_code == (
        200 if allowed else 403
    )
    assert post(client, gallery).status_code == (201 if allowed else 403)


def test_unrelated_user_cannot_view_or_upload(client, gallery, db_session):
    assert not permissions(gallery, db_session, 3).can_view_gallery
    assert not permissions(gallery, db_session, 3).can_upload_photo
    assert client.get(path(gallery), headers=gallery[4][3]).status_code == 403
    assert post(client, gallery, 3).status_code == 403
    assert not gallery[2].puts


def test_organizer_view_only_unless_checked_in(client, gallery, db_session):
    p = permissions(gallery, db_session, 0)
    assert p.can_view_gallery and not p.can_upload_photo
    assert client.get(path(gallery), headers=gallery[4][0]).status_code == 200
    assert post(client, gallery, 0).status_code == 403
    set_status(db_session, gallery[0].id, gallery[1][0].id, "COMPLETED")
    db_session.commit()
    assert permissions(gallery, db_session, 0).can_upload_photo
    assert post(client, gallery, 0).status_code == 201


@pytest.mark.parametrize(
    "offset,allowed", [(-1, True), (1, True), (72, False), (73, False)]
)
@pytest.mark.parametrize("user", [0, 1])
def test_time_boundaries_and_permissions(
    client, gallery, db_session, offset, allowed, user
):
    photo = post(client, gallery).json()
    gallery[3][0] = END + timedelta(hours=offset)
    p = permissions(gallery, db_session, user)
    assert p.can_view_gallery == allowed
    assert p.can_upload_photo == (allowed and user == 1)
    assert client.get(path(gallery), headers=gallery[4][user]).status_code == (
        200 if allowed else 403
    )
    assert post(client, gallery, user).status_code == (
        201 if allowed and user == 1 else 403
    )
    if not allowed:
        assert (
            client.delete(
                path(gallery) + f"/{photo['id']}", headers=gallery[4][1]
            ).status_code
            == 403
        )
        assert count(db_session) == 1  # Expiry never cleans up persisted content.


def test_one_microsecond_before_closure_is_open(client, gallery):
    gallery[3][0] = END + timedelta(hours=72) - timedelta(microseconds=1)
    assert post(client, gallery).status_code == 201


def test_cancel_preserves_gallery_and_own_delete_blocks_new_uploads(
    client, gallery, db_session
):
    photo = post(client, gallery).json()
    gallery[0].cancelled_at = NOW
    db_session.commit()
    p = permissions(gallery, db_session)
    assert p.can_view_gallery and not p.can_upload_photo
    for user in (0, 1):
        assert (
            client.get(path(gallery), headers=gallery[4][user]).json()[0]["id"]
            == photo["id"]
        )
    assert post(client, gallery).status_code == 403
    assert count(db_session) == 1
    assert (
        client.delete(
            path(gallery) + f"/{photo['id']}", headers=gallery[4][1]
        ).status_code
        == 204
    )
    assert count(db_session) == 0


def test_three_photos_each_user_limit_and_delete_frees_slot(
    client, gallery, db_session
):
    first = None
    for user in (1, 2):
        for _ in range(3):
            response = post(client, gallery, user)
            assert response.status_code == 201
            first = response.json()
        assert post(client, gallery, user).status_code == 409
    assert count(db_session) == 6
    assert (
        client.delete(
            path(gallery) + f"/{first['id']}", headers=gallery[4][2]
        ).status_code
        == 204
    )
    assert post(client, gallery, 2).status_code == 201


@pytest.mark.parametrize(
    "format,mime",
    [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")],
)
def test_formats_validated_and_safe_key_ignores_filename(
    client, gallery, db_session, format, mime
):
    data = image_bytes(format)
    result = post(client, gallery, data=data, mime=mime)
    assert result.status_code == 201
    photo = db_session.get(ActivityPhoto, UUID(result.json()["id"]))
    assert photo.content_type == mime
    assert photo.size_bytes == len(data)
    assert gallery[2].objects[photo.object_key] == data
    assert (
        photo.object_key
        == f"activities/{gallery[0].id}/{photo.id}."
        + {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}[format]
    )


@pytest.mark.parametrize(
    "data,mime",
    [
        (image_bytes("GIF"), "image/gif"),
        (image_bytes("GIF"), "image/jpeg"),
        (b"<svg onload='alert(1)'/>", "image/svg+xml"),
        (b"<svg/>", "image/png"),
        (b"not a jpeg", "image/jpeg"),
        (image_bytes(), "image/png"),
        (image_bytes(), "application/octet-stream"),
        (image_bytes()[:-20], "image/jpeg"),
        (image_bytes("PNG")[:-20], "image/png"),
        (b"", "image/jpeg"),
        (b"%PDF-data", "application/pdf"),
    ],
)
def test_invalid_files_rejected_without_storage(
    client, gallery, db_session, data, mime
):
    assert post(client, gallery, data=data, mime=mime).status_code == 422
    assert count(db_session) == 0
    assert not gallery[2].puts


def test_missing_file_and_oversize(client, gallery):
    assert client.post(path(gallery), headers=gallery[4][1]).status_code == 422
    assert post(client, gallery, data=b"x" * (MAX_PHOTO_BYTES + 1)).status_code == 413
    assert not gallery[2].puts


def test_bounded_reader_accepts_exact_limit_aborts_without_reading_all():
    class BoundedStream(BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 64 * 1024
            return super().read(size)

    assert len(read_bounded(BoundedStream(b"x" * MAX_PHOTO_BYTES))) == MAX_PHOTO_BYTES
    stream = BoundedStream(b"x" * (MAX_PHOTO_BYTES + 200000))
    with pytest.raises(PhotoValidationError) as exc:
        read_bounded(stream)
    assert exc.value.status_code == 413
    assert stream.tell() == MAX_PHOTO_BYTES + 1


def test_gallery_order_safe_projection_urls_and_query_count(
    client, gallery, db_session
):
    photos = [post(client, gallery, user).json() for user in (2, 1, 2)]
    statements = []
    engine = db_session.get_bind()

    def record(_conn, _cursor, statement, *_):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        response = client.get(path(gallery), headers=gallery[4][1])
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["vary"] == "Authorization"
    assert [p["id"] for p in response.json()] == sorted(p["id"] for p in photos)
    assert (
        len(statements) == 4
    )  # auth, activity, participation status, photos JOIN uploader
    for photo in response.json():
        assert set(photo) == {
            "id",
            "activity_id",
            "uploader",
            "created_at",
            "content_type",
            "size_bytes",
            "url",
        }
        assert set(photo["uploader"]) == {"id", "display_name", "avatar_url"}
        assert "signed=" in photo["url"]
    assert "url" not in ActivityPhoto.__table__.columns
    assert "password_hash" not in statements[-1] and "email" not in statements[-1]
    assert len(gallery[2].signs) == 6
    detail = client.get(f"/api/v1/activities/{gallery[0].id}").json()
    assert not detail["permissions"]["can_view_gallery"]
    assert not detail["permissions"]["can_upload_photo"]
    assert "photos" not in detail and "storage.invalid" not in str(detail)


@pytest.mark.parametrize("user,expected", [(0, 403), (1, 204), (2, 403), (3, 403)])
def test_only_uploader_deletes(client, gallery, db_session, user, expected):
    photo = post(client, gallery).json()
    response = client.delete(
        path(gallery) + f"/{photo['id']}", headers=gallery[4][user]
    )
    assert response.status_code == expected
    assert count(db_session) == (0 if expected == 204 else 1)
    if expected == 204:
        assert response.content == b""
        assert len(gallery[2].deletes) == 1
        assert not gallery[2].objects


def test_unknown_and_mismatched_photo_or_activity(client, gallery):
    photo = post(client, gallery).json()
    assert (
        client.delete(path(gallery) + f"/{uuid4()}", headers=gallery[4][1]).status_code
        == 404
    )
    for method in ("get", "post", "delete"):
        url = f"/api/v1/activities/{uuid4()}/photos" + (
            f"/{photo['id']}" if method == "delete" else ""
        )
        kwargs = (
            {"files": {"file": ("x", image_bytes(), "image/jpeg")}}
            if method == "post"
            else {}
        )
        assert (
            getattr(client, method)(url, headers=gallery[4][1], **kwargs).status_code
            == 404
        )


def test_photo_must_belong_to_requested_existing_activity(client, gallery, db_session):
    photo = post(client, gallery).json()
    other, _ = seed(db_session)
    response = client.delete(
        f"/api/v1/activities/{other.id}/photos/{photo['id']}", headers=gallery[4][1]
    )
    assert response.status_code == 404
    assert count(db_session) == 1 and not gallery[2].deletes


def test_storage_delete_failure_keeps_metadata_then_missing_object_retry_succeeds(
    client, gallery, db_session
):
    photo = post(client, gallery).json()
    gallery[2].fail_delete = True
    url = path(gallery) + f"/{photo['id']}"
    response = client.delete(url, headers=gallery[4][1])
    assert response.status_code == 503
    assert response.json() == {"detail": "Photo storage unavailable"}
    assert count(db_session) == 1
    gallery[2].fail_delete = False
    gallery[2].objects.clear()  # Already missing storage object is recoverable.
    assert client.delete(url, headers=gallery[4][1]).status_code == 204
    assert count(db_session) == 0


def test_upload_storage_failure_inserts_no_metadata(client, gallery, db_session):
    gallery[2].fail_put = True
    assert post(client, gallery).status_code == 503
    assert count(db_session) == 0
    assert len(gallery[2].puts) == len(gallery[2].deletes) == 1


@pytest.mark.parametrize("failure", ["flush", "commit"])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_db_failure_compensates_or_logs_original_error(
    gallery, db_session, monkeypatch, caplog, failure, cleanup_fails
):
    gallery[2].fail_delete = cleanup_fails

    def fail():
        raise SQLAlchemyError("simulated DB failure")

    monkeypatch.setattr(db_session, failure, fail)
    with pytest.raises(SQLAlchemyError, match="simulated DB failure"):
        gallery_service.upload_photo(
            db_session,
            gallery[0].id,
            gallery[1][1].id,
            BytesIO(image_bytes()),
            "image/jpeg",
            gallery[2],
        )
    assert count(db_session) == 0
    assert len(gallery[2].deletes) == 1
    assert bool(gallery[2].objects) == cleanup_fails
    assert ("orphan object requires cleanup" in caplog.text) == cleanup_fails


def test_sign_failure_compensates_upload_and_get_returns_failure(
    client, gallery, db_session
):
    gallery[2].fail_sign = True
    assert post(client, gallery).status_code == 503
    assert count(db_session) == 0 and not gallery[2].objects
    gallery[2].fail_sign = False
    assert post(client, gallery).status_code == 201
    gallery[2].fail_sign = True
    assert client.get(path(gallery), headers=gallery[4][1]).status_code == 503


def test_delete_commit_failure_preserves_metadata_and_retry_recovers(
    gallery, db_session, monkeypatch, caplog
):
    photo = gallery_service.upload_photo(
        db_session,
        gallery[0].id,
        gallery[1][1].id,
        BytesIO(image_bytes()),
        "image/jpeg",
        gallery[2],
    )
    original = db_session.commit

    def fail():
        raise SQLAlchemyError("delete commit failed")

    monkeypatch.setattr(db_session, "commit", fail)
    with pytest.raises(SQLAlchemyError):
        gallery_service.delete_photo(
            db_session, gallery[0].id, photo.id, gallery[1][1].id, gallery[2]
        )
    assert count(db_session) == 1 and not gallery[2].objects
    assert "retry photo" in caplog.text
    monkeypatch.setattr(db_session, "commit", original)
    gallery_service.delete_photo(
        db_session, gallery[0].id, photo.id, gallery[1][1].id, gallery[2]
    )
    assert count(db_session) == 0


def test_upload_rechecks_clock_after_validation(gallery, db_session):
    clock = iter([NOW, END + timedelta(hours=72)])
    with pytest.raises(gallery_service.GalleryError):
        gallery_service.upload_photo(
            db_session,
            gallery[0].id,
            gallery[1][1].id,
            BytesIO(image_bytes()),
            "image/jpeg",
            gallery[2],
            clock=lambda: next(clock),
        )
    assert not gallery[2].puts and count(db_session) == 0


def test_near_close_url_ttl_is_bounded(client, gallery):
    gallery[3][0] = END + timedelta(hours=72) - timedelta(seconds=20)
    assert post(client, gallery).status_code == 201
    assert gallery[2].signs[-1][1] == 20


def test_gallery_openapi_file_upload_contract(client):
    schema = client.get("/openapi.json").json()
    paths = schema["paths"]["/api/v1/activities/{activity_id}/photos"]
    for method in ("get", "post"):
        assert paths[method]["security"] == [{"OAuth2PasswordBearer": []}]
        assert paths[method]["tags"] == ["Activity Photos"]
    upload = paths["post"]
    content = upload["requestBody"]["content"]["multipart/form-data"]["schema"]
    body = schema["components"]["schemas"][content["$ref"].split("/")[-1]]
    assert body["required"] == ["file"]
    assert body["properties"]["file"]["format"] == "binary"
    assert {"201", "401", "403", "404", "409", "413", "422", "503"} <= upload[
        "responses"
    ].keys()
    dto = schema["components"]["schemas"]["ActivityPhotoRead"]["properties"]
    assert "object_key" not in dto and "url" in dto
    assert schema["paths"]["/api/v1/activities/{activity_id}/photos/{photo_id}"][
        "delete"
    ]["security"]
