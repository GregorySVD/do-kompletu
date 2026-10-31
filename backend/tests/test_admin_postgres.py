"""Real persistence, rollback and parent-row contention for admin moderation."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
import test_activity_management_postgres as pg_data
from admin_data import photo_path, seed_admin
from gallery_data import END, image_bytes
from sqlalchemy import delete, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from test_activity_management_postgres import pg_client, wait_for_lock_waiters

from app.core.security import hash_password
from app.main import app
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.activity_photo import ActivityPhoto
from app.models.user import User
from app.services import activity_management_service as management
from app.services.activity_service import get_activity_for_update
from app.services.participation_service import ParticipationError, join_activity

pg_engine = pg_data.pg_engine
pg_activity = pg_data.pg_activity
pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


@pytest.fixture
def pg_admin(pg_engine, monkeypatch):
    previous = app.dependency_overrides.copy()
    with Session(pg_engine, expire_on_commit=False) as session:
        context = seed_admin(session, monkeypatch)
    try:
        yield context
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        with pg_engine.begin() as connection:
            activity_id = context[0].id
            connection.execute(
                delete(ActivityPhoto).where(ActivityPhoto.activity_id == activity_id)
            )
            connection.execute(delete(Activity).where(Activity.id == activity_id))
            connection.execute(
                delete(User).where(User.id.in_([u.id for u in context[1]]))
            )


def test_pg_activation_persistence_and_preissued_tokens(pg_engine, pg_admin):
    context = pg_admin
    user_id = context[1][1].id
    with Session(pg_engine) as session:
        session.get(User, user_id).password_hash = hash_password("SecretPass123")
        session.commit()
    with pg_client(pg_engine) as client:
        credentials = {"identifier": context[1][1].email, "password": "SecretPass123"}
        login = client.post("/api/v1/auth/login", json=credentials)
        assert login.status_code == 200
        tokens = login.json()
        access = {"Authorization": f"Bearer {tokens['access_token']}"}
        path = f"/api/v1/admin/users/{user_id}/active"
        response = client.patch(path, headers=context[4][3], json={"is_active": False})
        assert response.status_code == 200 and response.json()["is_active"] is False
        with Session(pg_engine) as observer:
            user = observer.get(User, user_id)
            assert not user.is_active and not user.is_admin and user.points_total == 37
        assert client.get("/api/v1/users/me", headers=access).status_code == 401
        assert client.post("/api/v1/auth/login", json=credentials).status_code == 401
        assert (
            client.post(
                "/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
            ).status_code
            == 401
        )
        assert (
            client.patch(
                path, headers=context[4][3], json={"is_active": True}
            ).status_code
            == 200
        )
        assert client.post("/api/v1/auth/login", json=credentials).status_code == 200
        with Session(pg_engine) as observer:
            assert observer.get(User, user_id).is_active
        # The original admin token also loses access following DB deactivation.
        assert (
            client.get("/api/v1/admin/users", headers=context[4][3]).status_code == 200
        )
        with Session(pg_engine) as session:
            session.get(User, context[1][3].id).is_active = False
            session.commit()
        assert (
            client.get("/api/v1/admin/users", headers=context[4][3]).status_code == 401
        )


@pytest.mark.parametrize("failure", [False, True])
def test_pg_admin_photo_delete_after_closure_storage_consistency(
    pg_engine, pg_admin, failure
):
    context = pg_admin
    with pg_client(pg_engine) as client:
        result = client.post(
            photo_path(context),
            headers=context[4][1],
            files={"file": ("p.jpg", image_bytes(), "image/jpeg")},
        )
        assert result.status_code == 201
        photo_id = UUID(result.json()["id"])
        with Session(pg_engine) as observer:
            key = observer.get(ActivityPhoto, photo_id).object_key
        context[3][0] = END + timedelta(hours=73)
        assert client.get(photo_path(context), headers=context[4][3]).status_code == 403
        context[2].fail_delete = failure
        response = client.delete(
            f"{photo_path(context)}/{photo_id}", headers=context[4][3]
        )
        assert response.status_code == (503 if failure else 204)
        with Session(pg_engine) as observer:
            assert (observer.get(ActivityPhoto, photo_id) is not None) is failure
        assert (key in context[2].objects) is failure
        if failure:
            assert response.json() == {"detail": "Photo storage unavailable"}
            context[2].fail_delete = False
            assert (
                client.delete(
                    f"{photo_path(context)}/{photo_id}", headers=context[4][3]
                ).status_code
                == 204
            )


def test_pg_admin_cancel_http_preserves_evidence(pg_engine, pg_admin):
    context = pg_admin
    with Session(pg_engine) as session:
        before = session.execute(
            select(ActivityParticipation.__table__).where(
                ActivityParticipation.activity_id == context[0].id
            )
        ).all()
    with pg_client(pg_engine) as client:
        result = client.post(
            photo_path(context),
            headers=context[4][1],
            files={"file": ("p.jpg", image_bytes(), "image/jpeg")},
        )
        assert result.status_code == 201
        path = f"/api/v1/admin/activities/{context[0].id}/cancel"
        response = client.post(path, headers=context[4][3])
        assert response.status_code == 200 and response.json()["status"] == "CANCELLED"
        assert client.post(path, headers=context[4][3]).status_code == 409
        assert str(context[0].id) not in [
            r["id"] for r in client.get("/api/v1/activities").json()
        ]
        detail = client.get(
            f"/api/v1/activities/{context[0].id}", headers=context[4][1]
        ).json()
        assert detail["current_user_participation"]["checked_in_at"]
        assert (
            client.get(photo_path(context), headers=context[4][1]).json()[0]["id"]
            == result.json()["id"]
        )
        listing = client.get("/api/v1/admin/activities", headers=context[4][3]).json()
        assert any(
            r["id"] == str(context[0].id) and r["status"] == "CANCELLED"
            for r in listing
        )
        assert "checked_in_at" not in str(listing) and "email" not in str(listing)
    with Session(pg_engine) as observer:
        assert (
            observer.execute(
                select(ActivityParticipation.__table__).where(
                    ActivityParticipation.activity_id == context[0].id
                )
            ).all()
            == before
        )
        assert observer.get(ActivityPhoto, UUID(result.json()["id"])) is not None


@pytest.mark.parametrize("scenario", ["join", "organizer_cancel"])
@pytest.mark.parametrize("admin_first", [True, False])
def test_pg_admin_cancel_serializes_same_parent_lock(
    pg_engine, pg_activity, scenario, admin_first
):
    activity_id, users = pg_activity
    with Session(pg_engine) as session:
        session.get(User, users[4]).is_admin = True
        session.commit()
    name = "dk-admin-" + uuid4().hex

    def worker(admin):
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            session.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )
            cached = session.get(Activity, activity_id)
            assert cached.cancelled_at is None
            try:
                if admin:
                    actor = session.get(User, users[4])
                    management.cancel_activity(
                        session, activity_id, actor.id, is_admin=actor.is_admin
                    )
                elif scenario == "join":
                    join_activity(session, activity_id, users[3])
                else:
                    management.cancel_activity(session, activity_id, users[0])
                return 200
            except (management.ActivityManagementError, ParticipationError) as exc:
                return exc.status_code

    with Session(pg_engine) as holder, ThreadPoolExecutor(max_workers=2) as pool:
        get_activity_for_update(holder, activity_id)
        try:
            first = pool.submit(worker, admin_first)
            wait_for_lock_waiters(pg_engine, name, 1)
            second = pool.submit(worker, not admin_first)
            wait_for_lock_waiters(pg_engine, name, 2)
        finally:
            holder.rollback()
        outcomes = [first.result(timeout=15), second.result(timeout=15)]
    assert outcomes == (
        [200, 200] if scenario == "join" and not admin_first else [200, 409]
    )
    with Session(pg_engine) as observer:
        assert observer.get(Activity, activity_id).cancelled_at is not None
        rows = observer.scalars(
            select(ActivityParticipation).where(
                ActivityParticipation.activity_id == activity_id
            )
        ).all()
        assert len(rows) == (3 if scenario == "join" and not admin_first else 2)


def test_pg_admin_cancel_rolls_back_on_snapshot_failure(
    pg_engine, pg_admin, monkeypatch
):
    def fail(session, activity_id, user_id, now):
        assert session.get(Activity, activity_id).cancelled_at is not None
        raise SQLAlchemyError("snapshot failure")

    monkeypatch.setattr(management, "_snapshot", fail)
    with pg_client(pg_engine) as client, pytest.raises(SQLAlchemyError):
        client.post(
            f"/api/v1/admin/activities/{pg_admin[0].id}/cancel",
            headers=pg_admin[4][3],
        )
    with Session(pg_engine) as observer:
        assert observer.get(Activity, pg_admin[0].id).cancelled_at is None
