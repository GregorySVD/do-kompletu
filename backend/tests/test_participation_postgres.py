from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.activity import Activity
from app.models.activity_participation import (
    ACTIVE_PARTICIPATION_STATUSES,
    ActivityParticipation,
)
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCreate
from app.services.activity_service import (
    activity_to_read,
    create_activity,
    get_activity_by_id,
)
from app.services.participation_service import (
    ParticipationError,
    join_activity,
    leave_activity,
)

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    POSTGRES_TEST_DATABASE_URL is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


@pytest.fixture
def pg_engine():
    engine = create_engine(
        POSTGRES_TEST_DATABASE_URL,
        isolation_level="READ COMMITTED",
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=15000 -c lock_timeout=10000",
        },
    )
    assert engine.dialect.name == "postgresql"
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_activity(pg_engine):
    """Commit only test-owned UUIDs for multi-connection tests; remove them afterward."""
    activity_id = None
    user_ids = []
    try:
        with Session(pg_engine, expire_on_commit=False) as session:
            suffix = uuid4().hex
            users = [
                User(
                    email=f"participation-{suffix}-{i}@example.com",
                    display_name=f"Participation{suffix}{i}",
                    password_hash="unused-in-token-tests",
                )
                for i in range(5)
            ]
            session.add_all(users)
            session.commit()
            user_ids = [user.id for user in users]
            result = create_activity(
                session,
                ActivityCreate.model_validate(
                    {
                        **ACTIVITY_CREATE_EXAMPLE,
                        "min_participants": 2,
                        "max_participants": 2,
                    }
                ),
                users[0],
            )
            activity_id = result.activity.id
        yield activity_id, user_ids
    finally:
        with pg_engine.begin() as connection:
            if activity_id is not None:
                connection.execute(delete(Activity).where(Activity.id == activity_id))
            if user_ids:
                connection.execute(delete(User).where(User.id.in_(user_ids)))


def test_postgres_membership_schema(pg_engine):
    inspector = inspect(pg_engine)
    primary_key = inspector.get_pk_constraint("activity_participations")
    assert primary_key["name"] == "pk_activity_participations"
    assert primary_key["constrained_columns"] == ["activity_id", "user_id"]
    columns = {
        column["name"]: column
        for column in inspector.get_columns("activity_participations")
    }
    assert set(columns) == {
        "activity_id",
        "user_id",
        "joined_at",
        "status",
        "left_at",
        "confirmed_at",
        "checked_in_at",
        "completed_at",
        "no_show_at",
        "waitlisted_at",
        "confirmation_expired_at",
        "waitlist_expired_at",
    }
    assert all(
        not columns[name]["nullable"] for name in ("activity_id", "user_id", "status")
    )
    assert columns["left_at"]["nullable"] and columns["confirmed_at"]["nullable"]
    assert columns["joined_at"]["nullable"] and columns["waitlisted_at"]["nullable"]
    assert "JOINED" in columns["status"]["default"]
    assert columns["joined_at"]["type"].timezone is True
    assert columns["joined_at"]["default"] is not None
    foreign_keys = inspector.get_foreign_keys("activity_participations")
    assert {key["referred_table"] for key in foreign_keys} == {"users", "activities"}
    assert all(key["options"]["ondelete"] == "CASCADE" for key in foreign_keys)
    assert any(
        index["column_names"] == ["user_id"]
        for index in inspector.get_indexes("activity_participations")
    )


def test_postgres_unique_constraint_and_server_timestamp(pg_engine, pg_activity):
    activity_id, users = pg_activity
    with Session(pg_engine) as session:
        values = {"activity": activity_id, "user": users[1]}
        statement = text(
            "INSERT INTO activity_participations (activity_id, user_id) "
            "VALUES (:activity, :user) RETURNING joined_at"
        )
        joined_at = session.scalar(statement, values)
        assert joined_at.tzinfo is not None
        with pytest.raises(IntegrityError) as caught, session.begin_nested():
            session.execute(statement, values)
        assert caught.value.orig.sqlstate == "23505"
        assert caught.value.orig.diag.constraint_name == "pk_activity_participations"
        assert (
            session.scalar(
                select(func.count())
                .select_from(ActivityParticipation)
                .where(ActivityParticipation.activity_id == activity_id)
            )
            == 1
        )


@pytest.mark.parametrize("missing", ["user", "activity"])
def test_postgres_foreign_keys(pg_engine, pg_activity, missing):
    activity_id, users = pg_activity
    with Session(pg_engine) as session:
        with pytest.raises(IntegrityError) as caught, session.begin_nested():
            session.add(
                ActivityParticipation(
                    activity_id=uuid4() if missing == "activity" else activity_id,
                    user_id=uuid4() if missing == "user" else users[1],
                )
            )
            session.flush()
        assert caught.value.orig.sqlstate == "23503"


@pytest.mark.parametrize("deleted", ["user", "activity"])
def test_postgres_membership_cascades(pg_engine, pg_activity, deleted):
    activity_id, users = pg_activity
    with Session(pg_engine, expire_on_commit=False) as session:
        join_activity(session, activity_id, users[1])
        statement = (
            delete(Activity).where(Activity.id == activity_id)
            if deleted == "activity"
            else delete(User).where(User.id == users[1])
        )
        session.execute(statement)
        session.commit()
        assert (
            session.scalar(
                select(func.count())
                .select_from(ActivityParticipation)
                .where(ActivityParticipation.activity_id == activity_id)
            )
            == 0
        )


def test_postgres_http_join_detail_list_and_leave(pg_engine, pg_activity):
    activity_id, users = pg_activity

    def database():
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            yield session

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            path = f"/api/v1/activities/{activity_id}"
            headers = {"Authorization": f"Bearer {create_access_token(users[1])}"}
            joined = client.post(f"{path}/join", headers=headers)
            assert joined.status_code == 201
            body = joined.json()
            assert body["participant_count"] == body["available_slots"] == 1
            assert body["latitude"] == pytest.approx(
                ACTIVITY_CREATE_EXAMPLE["latitude"]
            )
            assert body["longitude"] == pytest.approx(
                ACTIVITY_CREATE_EXAMPLE["longitude"]
            )
            assert body["current_user_participation"]["status"] == "JOINED"
            assert client.get(path, headers=headers).json() == body
            anonymous = client.get(path).json()
            assert anonymous["current_user_participation"] is None
            assert not any(anonymous["permissions"].values())
            cards = client.get("/api/v1/activities", params={"limit": 100}).json()
            card = next(card for card in cards if card["id"] == str(activity_id))
            assert card["participant_count"] == 1
            assert client.post(f"{path}/join", headers=headers).status_code == 409
            left = client.delete(f"{path}/join", headers=headers)
            assert left.status_code == 200
            assert left.json()["participant_count"] == 0
            assert left.json()["available_slots"] == 2
            assert left.json()["current_user_participation"] is None
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize("scenario", ["final_place", "duplicate", "join_leave"])
def test_postgres_concurrent_membership_serializes_on_activity(
    pg_engine, pg_activity, scenario
):
    activity_id, users = pg_activity
    with Session(pg_engine, expire_on_commit=False) as session:
        join_activity(session, activity_id, users[1])
        if scenario == "join_leave":
            join_activity(session, activity_id, users[2])

    name = f"dk-capacity-{uuid4().hex}"
    barrier = Barrier(3)

    def worker(user_id, operation):
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            session.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )
            barrier.wait(timeout=5)
            try:
                operation(session, activity_id, user_id)
                return 200 if operation is leave_activity else 201
            except ParticipationError as exc:
                return exc.status_code, str(exc)

    operations = (
        [(users[1], leave_activity), (users[3], join_activity)]
        if scenario == "join_leave"
        else [
            (users[2], join_activity),
            (users[2] if scenario == "duplicate" else users[3], join_activity),
        ]
    )
    # Hold the same row so both workers must overlap and visibly wait in PostgreSQL.
    # This tests actual blocking, rather than hoping the thread scheduler creates a race.
    with Session(pg_engine) as holder, ThreadPoolExecutor(max_workers=2) as executor:
        holder.scalar(
            select(Activity).where(Activity.id == activity_id).with_for_update()
        )
        futures = [executor.submit(worker, *operation) for operation in operations]
        try:
            barrier.wait(timeout=5)
            deadline = time.monotonic() + 5
            blocked = 0
            while time.monotonic() < deadline:
                with pg_engine.connect() as observer:
                    blocked = observer.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity "
                            "WHERE application_name = :name AND wait_event_type = 'Lock'"
                        ),
                        {"name": name},
                    )
                if blocked == 2:
                    break
                time.sleep(0.02)
            assert blocked == 2, (
                "Both membership writers must wait on real PostgreSQL locks"
            )
        finally:
            holder.rollback()
        outcomes = [future.result(timeout=10) for future in futures]

    with Session(pg_engine) as session:
        result = activity_to_read(get_activity_by_id(session, activity_id))
        count = session.scalar(
            select(func.count())
            .select_from(ActivityParticipation)
            .where(
                ActivityParticipation.activity_id == activity_id,
                ActivityParticipation.status.in_(ACTIVE_PARTICIPATION_STATUSES),
            )
        )
        assert result.participant_count == count <= 2
        assert result.available_slots == 2 - count
        if scenario == "join_leave":
            assert outcomes[0] == 200
            assert outcomes[1] == 201
            assert count == 2
            assert (
                session.get(ActivityParticipation, (activity_id, users[1])).status
                == "LEFT"
            )
        elif scenario == "duplicate":
            assert outcomes.count(201) == 1
            assert outcomes.count((409, "Already joined this activity")) == 1
            assert count == 2
        else:
            assert outcomes.count(201) == 2
            assert count == 2 and result.waitlist_count == 1
