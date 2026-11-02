from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from admin_data import photo_path, seed_admin
from gallery_data import END, NOW, image_bytes, set_status
from jose import jwt
from sqlalchemy import event, select
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.activity_photo import ActivityPhoto
from app.models.user import User
from app.services import activity_management_service


@pytest.fixture
def context(client, db_session, monkeypatch):
    return seed_admin(db_session, monkeypatch)


def admin_request(client, context, operation, headers):
    path = "/api/v1/admin"
    if operation == "users":
        return client.get(path + "/users", headers=headers)
    if operation == "activities":
        return client.get(path + "/activities", headers=headers)
    if operation == "active":
        return client.patch(
            f"{path}/users/{context[1][1].id}/active",
            headers=headers,
            json={"is_active": False},
        )
    return client.post(f"{path}/activities/{context[0].id}/cancel", headers=headers)


@pytest.mark.parametrize("operation", ["users", "activities", "active", "cancel"])
@pytest.mark.parametrize("identity,expected", [(None, 401), (1, 403), (3, 200)])
def test_all_admin_endpoints_authorization(
    client, context, operation, identity, expected
):
    headers = {} if identity is None else context[4][identity]
    response = admin_request(client, context, operation, headers)
    assert response.status_code == expected, response.text
    if expected == 200:
        assert response.headers["Cache-Control"] == "private, no-store"
        assert response.headers["Vary"] == "Authorization"


@pytest.mark.parametrize("operation", ["users", "activities", "active", "cancel"])
def test_already_issued_admin_token_rejected_after_deactivation(
    client, context, db_session, operation
):
    token = context[4][3]  # Issued while active.
    assert client.get("/api/v1/admin/users", headers=token).status_code == 200
    context[1][3].is_active = False
    db_session.commit()
    assert admin_request(client, context, operation, token).status_code == 401


@pytest.mark.parametrize("kind", ["invalid", "refresh", "deleted", "demoted", "claim"])
def test_admin_authorization_uses_database_not_token_privilege(
    client, context, db_session, kind
):
    if kind == "demoted":
        context[1][3].is_admin = False
        db_session.commit()
        headers, expected = context[4][3], 403
    elif kind == "claim":
        settings = get_settings()
        claims = jwt.get_unverified_claims(create_access_token(context[1][1].id))
        claims["is_admin"] = True
        token = jwt.encode(
            claims, settings.jwt_secret, algorithm=settings.jwt_algorithm
        )
        headers, expected = {"Authorization": f"Bearer {token}"}, 403
    else:
        token = {
            "invalid": "invalid",
            "refresh": create_refresh_token(context[1][3].id),
            "deleted": create_access_token(uuid4()),
        }[kind]
        headers, expected = {"Authorization": f"Bearer {token}"}, 401
    assert client.get("/api/v1/admin/users", headers=headers).status_code == expected


def test_user_list_fields_privacy_stable_order_pagination(client, context, db_session):
    for user in context[1]:
        user.created_at = NOW
    context[1][2].is_active = False
    db_session.commit()
    headers = context[4][3]
    rows = client.get("/api/v1/admin/users", headers=headers).json()
    assert [r["id"] for r in rows] == sorted(str(u.id) for u in context[1])
    assert all(
        set(r)
        == {
            "id",
            "email",
            "display_name",
            "is_active",
            "is_admin",
            "points_total",
            "created_at",
        }
        for r in rows
    )
    participant = next(r for r in rows if r["id"] == str(context[1][1].id))
    assert participant["email"] == context[1][1].email
    assert participant["points_total"] == 37
    assert sum(r["is_admin"] for r in rows) == 1
    assert any(not r["is_active"] for r in rows)
    assert "password_hash" not in str(rows)
    page = client.get("/api/v1/admin/users?limit=2&offset=1", headers=headers).json()
    assert page == rows[1:3]
    assert client.get("/api/v1/admin/users?offset=99", headers=headers).json() == []
    # Timestamp is the primary key for ordering, ahead of the UUID tie-breaker.
    first = max(context[1], key=lambda u: u.id)
    first.created_at = NOW - timedelta(days=1)
    db_session.commit()
    assert client.get("/api/v1/admin/users", headers=headers).json()[0]["id"] == str(
        first.id
    )


@pytest.mark.parametrize("resource", ["users", "activities"])
@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "limit=x"])
def test_admin_pagination_validation(client, context, resource, query):
    assert (
        client.get(
            f"/api/v1/admin/{resource}?{query}", headers=context[4][3]
        ).status_code
        == 422
    )


def test_activation_roundtrip_rejects_login_access_refresh(client, context, db_session):
    target = context[1][1]
    target.password_hash = hash_password("SecretPass123")
    db_session.commit()
    credentials = {"identifier": target.email, "password": "SecretPass123"}
    login = client.post("/api/v1/auth/login", json=credentials)
    assert login.status_code == 200
    tokens = login.json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    path = f"/api/v1/admin/users/{target.id}/active"
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200
    for _ in range(2):
        result = client.patch(path, headers=context[4][3], json={"is_active": False})
        assert result.status_code == 200 and result.json()["is_active"] is False
    assert "password_hash" not in result.text
    db_session.refresh(target)
    assert target.is_active is False and target.points_total == 37
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )
    assert (
        client.patch(path, headers=context[4][3], json={"is_active": True}).status_code
        == 200
    )
    assert client.post("/api/v1/auth/login", json=credentials).status_code == 200
    assert client.get("/api/v1/users/me", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 200
    )


def test_activation_unknown_self_protection_and_no_privilege_changes(
    client, context, db_session
):
    path = "/api/v1/admin/users"
    headers = context[4][3]
    response = client.patch(
        f"{path}/{context[1][3].id}/active", headers=headers, json={"is_active": False}
    )
    assert response.status_code == 409
    assert response.json() == {"detail": "Administrators cannot deactivate themselves"}
    assert (
        client.patch(
            f"{path}/{context[1][3].id}/active",
            headers=headers,
            json={"is_active": True},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"{path}/{uuid4()}/active", headers=headers, json={"is_active": False}
        ).status_code
        == 404
    )
    db_session.refresh(context[1][3])
    assert context[1][3].is_active and context[1][3].is_admin


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"is_active": None},
        {"is_active": "false"},
        {"is_active": 0},
        {"is_active": True, "is_admin": True},
    ],
)
def test_activation_rejects_invalid_or_unknown_fields(client, context, body):
    assert (
        client.patch(
            f"/api/v1/admin/users/{context[1][1].id}/active",
            headers=context[4][3],
            json=body,
        ).status_code
        == 422
    )


def test_self_promotion_impossible_and_own_profile_exposes_admin(
    client, context, db_session
):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "no-promotion@example.com",
            "display_name": "NoPromotion",
            "password": "SecretPass123",
            "is_admin": True,
            "is_active": False,
        },
    )
    assert response.status_code == 201
    assert response.json()["is_admin"] is False and response.json()["is_active"] is True
    user = db_session.get(User, UUID(response.json()["id"]))
    assert user.is_admin is False
    # Preserve existing normal-schema semantics: unknown fields are ignored.
    for identity, expected in [(1, False), (3, True)]:
        response = client.patch(
            "/api/v1/users/me",
            headers=context[4][identity],
            json={"is_admin": not expected},
        )
        assert response.status_code == 200 and response.json()["is_admin"] is expected
        assert (
            client.get("/api/v1/users/me", headers=context[4][identity]).json()[
                "is_admin"
            ]
            is expected
        )


def test_activity_list_all_lifecycles_counts_privacy_and_order(
    client, context, db_session
):
    original = context[0]
    original.created_at = NOW
    set_status(db_session, original.id, context[1][2].id, "WAITLISTED")
    for i in range(3):
        db_session.add(
            Activity(
                id=uuid4(),
                organizer_id=original.organizer_id,
                title=f"State {i}",
                description=original.description,
                category=original.category,
                start_at=NOW + timedelta(days=i - 1, minutes=30),
                end_at=NOW + timedelta(days=i - 1, hours=2),
                cancelled_at=NOW if i == 2 else None,
                location_name=original.location_name,
                address=original.address,
                location=original.location,
                min_participants=2,
                max_participants=4,
                price_type="FREE",
                created_at=NOW,
            )
        )
    db_session.commit()
    headers = context[4][3]
    rows = client.get("/api/v1/admin/activities", headers=headers).json()
    assert len(rows) == 4
    assert [r["id"] for r in rows] == sorted(r["id"] for r in rows)
    assert {r["status"] for r in rows} == {"PUBLISHED", "ONGOING", "ENDED", "CANCELLED"}
    item = next(r for r in rows if r["id"] == str(original.id))
    assert item["participant_count"] == item["waitlist_count"] == 1
    assert set(item) == {
        "id",
        "title",
        "organizer",
        "status",
        "start_at",
        "end_at",
        "cancelled_at",
        "participant_count",
        "waitlist_count",
        "created_at",
    }
    assert set(item["organizer"]) == {"id", "display_name", "avatar_url"}
    assert not any(
        word in str(rows)
        for word in (
            "email",
            "password",
            "joined_at",
            "checked_in_at",
            "permissions",
            "is_admin",
        )
    )
    assert (
        client.get("/api/v1/admin/activities?limit=2&offset=1", headers=headers).json()
        == rows[1:3]
    )
    assert (
        client.get("/api/v1/admin/activities?offset=99", headers=headers).json() == []
    )
    original.created_at = NOW - timedelta(days=5)
    db_session.commit()
    assert client.get("/api/v1/admin/activities", headers=headers).json()[0][
        "id"
    ] == str(original.id)


def test_admin_cancel_reuses_service_preserves_evidence_gallery_and_blocks_mutations(
    client, context, db_session, monkeypatch
):
    upload = client.post(
        photo_path(context),
        headers=context[4][1],
        files={"file": ("p.jpg", image_bytes(), "image/jpeg")},
    )
    assert upload.status_code == 201
    before = db_session.execute(select(ActivityParticipation.__table__)).all()
    calls = []
    original = activity_management_service.get_activity_for_update

    def record(session, activity_id):
        calls.append(activity_id)
        return original(session, activity_id)

    monkeypatch.setattr(activity_management_service, "get_activity_for_update", record)
    response = client.post(
        f"/api/v1/admin/activities/{context[0].id}/cancel", headers=context[4][3]
    )
    assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
    assert calls == [context[0].id]
    assert response.json()["cancelled_at"] is not None
    assert db_session.execute(select(ActivityParticipation.__table__)).all() == before
    assert str(context[0].id) not in [
        r["id"] for r in client.get("/api/v1/activities").json()
    ]
    detail = client.get(
        f"/api/v1/activities/{context[0].id}", headers=context[4][1]
    ).json()
    assert (
        detail["status"] == "CANCELLED"
        and detail["current_user_participation"]["checked_in_at"]
    )
    assert set(detail["organizer"]) == {"id", "display_name", "avatar_url"}
    listed = client.get(photo_path(context), headers=context[4][1]).json()
    assert len(listed) == 1
    assert {k: v for k, v in listed[0].items() if k != "url"} == {
        k: v for k, v in upload.json().items() if k != "url"
    }
    base = f"/api/v1/activities/{context[0].id}"
    for method, suffix, body in [
        ("post", "join", None),
        ("delete", "join", None),
        ("post", "confirm", None),
        ("post", "check-in", {"latitude": 52.4, "longitude": 16.9, "accuracy_m": 20}),
    ]:
        kwargs = {} if body is None else {"json": body}
        assert (
            getattr(client, method)(
                f"{base}/{suffix}", headers=context[4][2], **kwargs
            ).status_code
            == 409
        )
    assert client.post(base + "/finalize", headers=context[4][0]).status_code == 409
    assert (
        client.post(
            photo_path(context),
            headers=context[4][1],
            files={"file": ("p.jpg", image_bytes(), "image/jpeg")},
        ).status_code
        == 403
    )
    assert context[2].objects and not context[2].deletes
    assert context[1][1].points_total == 37


@pytest.mark.parametrize(
    "state,expected,detail",
    [
        ("unknown", 404, "Activity not found"),
        ("ended", 409, "Activity has ended"),
        ("cancelled", 409, "Activity is cancelled"),
    ],
)
def test_admin_cancel_domain_errors(
    client, context, db_session, state, expected, detail
):
    activity_id = context[0].id
    if state == "unknown":
        activity_id = uuid4()
    elif state == "ended":
        context[3][0] = END
    else:
        context[0].cancelled_at = NOW
        db_session.commit()
    result = client.post(
        f"/api/v1/admin/activities/{activity_id}/cancel", headers=context[4][3]
    )
    assert result.status_code == expected and result.json() == {"detail": detail}


def test_repeated_admin_cancel_preserves_first_timestamp(client, context):
    path = f"/api/v1/admin/activities/{context[0].id}/cancel"
    first = client.post(path, headers=context[4][3])
    context[3][0] += timedelta(minutes=5)
    assert client.post(path, headers=context[4][3]).status_code == 409
    assert (
        client.get(f"/api/v1/activities/{context[0].id}").json()["cancelled_at"]
        == first.json()["cancelled_at"]
    )


def test_admin_cancellation_rollback_on_snapshot_failure(
    client, context, db_session, monkeypatch
):
    def fail(*args):
        raise SQLAlchemyError("snapshot failure")

    monkeypatch.setattr(activity_management_service, "_snapshot", fail)
    with pytest.raises(SQLAlchemyError):
        client.post(
            f"/api/v1/admin/activities/{context[0].id}/cancel", headers=context[4][3]
        )
    db_session.refresh(context[0])
    assert context[0].cancelled_at is None


@pytest.mark.parametrize(
    "identity,closed,expected",
    [
        (1, False, 204),
        (3, False, 204),
        (0, False, 403),
        (2, False, 403),
        (None, False, 401),
        (1, True, 403),
        (3, True, 204),
    ],
)
def test_photo_delete_authorization_and_expiry(
    client, context, db_session, identity, closed, expected
):
    result = client.post(
        photo_path(context),
        headers=context[4][1],
        files={"file": ("p.jpg", image_bytes(), "image/jpeg")},
    )
    photo_id = UUID(result.json()["id"])
    photo = db_session.get(ActivityPhoto, photo_id)
    key = photo.object_key
    if closed:
        context[3][0] = END + timedelta(hours=72)
    # Admin is unrelated; promotion never adds gallery GET permissions.
    assert client.get(photo_path(context), headers=context[4][3]).status_code == 403
    headers = {} if identity is None else context[4][identity]
    response = client.delete(f"{photo_path(context)}/{photo_id}", headers=headers)
    assert response.status_code == expected
    db_session.expire_all()
    assert (db_session.get(ActivityPhoto, photo_id) is None) == (expected == 204)
    assert (key not in context[2].objects) == (expected == 204)


@pytest.mark.parametrize("kind", ["storage", "commit"])
def test_admin_photo_failure_consistency(
    client, context, db_session, monkeypatch, kind
):
    result = client.post(
        photo_path(context),
        headers=context[4][1],
        files={"file": ("p.jpg", image_bytes(), "image/jpeg")},
    )
    photo_id = UUID(result.json()["id"])
    key = db_session.get(ActivityPhoto, photo_id).object_key
    context[3][0] = END + timedelta(hours=73)
    if kind == "storage":
        context[2].fail_delete = True
        response = client.delete(
            f"{photo_path(context)}/{photo_id}", headers=context[4][3]
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "Photo storage unavailable"}
        assert key in context[2].objects
    else:

        def fail(session):
            raise SQLAlchemyError("commit failure")

        event.listen(db_session.__class__, "before_commit", fail)
        try:
            with pytest.raises(SQLAlchemyError):
                client.delete(
                    f"{photo_path(context)}/{photo_id}", headers=context[4][3]
                )
        finally:
            event.remove(db_session.__class__, "before_commit", fail)
        assert key not in context[2].objects
    db_session.expire_all()
    assert db_session.get(ActivityPhoto, photo_id) is not None
    context[2].fail_delete = False
    assert (
        client.delete(
            f"{photo_path(context)}/{photo_id}", headers=context[4][3]
        ).status_code
        == 204
    )


@pytest.mark.parametrize("kind", ["activity", "photo", "mismatch", "inactive"])
def test_admin_photo_validation_and_inactive_rejection(
    client, context, db_session, kind
):
    result = client.post(
        photo_path(context),
        headers=context[4][1],
        files={"file": ("p.jpg", image_bytes(), "image/jpeg")},
    )
    photo_id = result.json()["id"]
    base = photo_path(context)
    if kind in {"activity", "mismatch"}:
        activity_id = uuid4()
        if kind == "mismatch":
            original = context[0]
            db_session.add(
                Activity(
                    id=activity_id,
                    organizer_id=original.organizer_id,
                    title="Other",
                    description=original.description,
                    category=original.category,
                    start_at=original.start_at,
                    end_at=original.end_at,
                    location=original.location,
                    location_name=original.location_name,
                    address=original.address,
                    min_participants=2,
                    price_type="FREE",
                )
            )
            db_session.commit()
        base = f"/api/v1/activities/{activity_id}/photos"
    elif kind == "photo":
        photo_id = uuid4()
    else:
        context[1][3].is_active = False
        db_session.commit()
    response = client.delete(f"{base}/{photo_id}", headers=context[4][3])
    assert response.status_code == (401 if kind == "inactive" else 404)
    assert context[2].objects and not context[2].deletes


def test_admin_openapi_contract(client):
    schema = client.get("/openapi.json").json()
    assert "Administration" in {t["name"] for t in schema["tags"]}
    expected = {
        "/api/v1/admin/users": "get",
        "/api/v1/admin/users/{user_id}/active": "patch",
        "/api/v1/admin/activities": "get",
        "/api/v1/admin/activities/{activity_id}/cancel": "post",
    }
    assert {p for p in schema["paths"] if p.startswith("/api/v1/admin")} == set(
        expected
    )
    for path, method in expected.items():
        operation = schema["paths"][path][method]
        assert operation["tags"] == ["Administration"]
        assert operation["security"] == [{"OAuth2PasswordBearer": []}]
        assert {"401", "403", "422"} <= set(operation["responses"])
        assert "Administrator authentication required" in operation["description"]
        if method != "get":
            assert {"404", "409"} <= set(operation["responses"])
        else:
            params = {p["name"]: p["schema"] for p in operation["parameters"]}
            assert (
                params["limit"]["default"] == 20 and params["limit"]["maximum"] == 100
            )
            assert params["offset"]["minimum"] == 0
    assert (
        schema["components"]["schemas"]["AdminUserActiveUpdate"]["additionalProperties"]
        is False
    )
    for name in ("AdminUserRead", "AdminActivityRead"):
        assert "password_hash" not in str(schema["components"]["schemas"][name])
    assert "is_admin" in schema["components"]["schemas"]["UserRead"]["properties"]
    for name in (
        "UserRegister",
        "UserUpdate",
        "ActivityOrganizerRead",
        "PhotoUploaderRead",
    ):
        assert "is_admin" not in schema["components"]["schemas"][name]["properties"]
