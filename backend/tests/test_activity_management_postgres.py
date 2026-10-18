from __future__ import annotations

import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event, func, inspect, select, text
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCreate
from app.schemas.activity_management import ActivityUpdate
from app.services.activity_management_service import (
    ActivityManagementError,
    cancel_activity,
    update_activity,
)
from app.services.activity_service import (
    activity_to_read,
    create_activity,
    get_activity_by_id,
)
from app.services.participation_service import ParticipationError, join_activity

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
    activity_id = None
    user_ids = []
    try:
        with Session(pg_engine, expire_on_commit=False) as session:
            suffix = uuid4().hex
            users = [
                User(
                    email=f"management-{suffix}-{i}@example.com",
                    display_name=f"Management{suffix}{i}",
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
                        "max_participants": 3,
                    }
                ),
                users[0],
            )
            activity_id = result.activity.id
            join_activity(session, activity_id, user_ids[1])
            join_activity(session, activity_id, user_ids[2])
        yield activity_id, user_ids
    finally:
        with pg_engine.begin() as connection:
            if activity_id is not None:
                connection.execute(delete(Activity).where(Activity.id == activity_id))
            if user_ids:
                connection.execute(delete(User).where(User.id.in_(user_ids)))


@contextmanager
def pg_client(engine):
    previous = app.dependency_overrides.copy()

    def database():
        with Session(engine, expire_on_commit=False, autoflush=False) as session:
            yield session

    app.dependency_overrides[get_db] = database
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)


def test_postgres_cancellation_schema(pg_engine):
    columns = {
        column["name"]: column
        for column in inspect(pg_engine).get_columns("activities")
    }
    assert columns["cancelled_at"]["nullable"] is True
    assert columns["cancelled_at"]["type"].timezone is True


@pytest.mark.parametrize("operation, expected_selects", [("patch", 4), ("cancel", 3)])
def test_postgres_management_http_response_and_query_count(
    pg_engine, pg_activity, operation, expected_selects
):
    activity_id, users = pg_activity
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    with pg_client(pg_engine) as client:
        event.listen(pg_engine, "before_cursor_execute", record)
        try:
            headers = {"Authorization": f"Bearer {create_access_token(users[0])}"}
            path = f"/api/v1/activities/{activity_id}"
            response = (
                client.patch(
                    path,
                    headers=headers,
                    json={
                        "latitude": 50.0664,
                        "price_type": "PAID",
                        "price_amount": 25.50,
                    },
                )
                if operation == "patch"
                else client.post(f"{path}/cancel", headers=headers)
            )
            assert response.status_code == 200, response.text
            assert len(statements) == expected_selects
            body = response.json()
            assert body["participant_count"] == 2
            assert body["available_slots"] == 1
            if operation == "patch":
                assert body["latitude"] == pytest.approx(50.0664)
                assert body["longitude"] == pytest.approx(
                    ACTIVITY_CREATE_EXAMPLE["longitude"]
                )
                assert body["price_amount"] == 25.5
                assert body["currency"] == "PLN"
            else:
                assert body["status"] == "CANCELLED"
                assert body["cancelled_at"].endswith("Z")
                assert not any(body["permissions"].values())
        finally:
            event.remove(pg_engine, "before_cursor_execute", record)


def test_postgres_cancellation_preserves_memberships_and_personal_visibility(
    pg_engine, pg_activity
):
    activity_id, users = pg_activity
    with Session(pg_engine, expire_on_commit=False) as session:
        result = cancel_activity(session, activity_id, users[0])
        assert result.participant_count == 2
        assert result.activity.cancelled_at.tzinfo is not None
    with pg_client(pg_engine) as client:
        assert str(activity_id) not in [
            item["id"] for item in client.get("/api/v1/activities").json()
        ]
        public = client.get(f"/api/v1/activities/{activity_id}").json()
        assert public["status"] == "CANCELLED"
        assert public["current_user_participation"] is None
        for user, relation in [(users[0], "organized"), (users[1], "joined")]:
            response = client.get(
                "/api/v1/users/me/activities",
                params={"relation": relation},
                headers={
                    "Authorization": f"Bearer {create_access_token(user)}",
                },
            )
            assert response.status_code == 200
            item = next(
                item for item in response.json() if item["id"] == str(activity_id)
            )
            assert item["participant_count"] == 2
            assert item["status"] == "CANCELLED"
            assert (item["current_user_participation"] is not None) is (
                relation == "joined"
            )


def wait_for_lock_waiters(engine, application_name, expected):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as observer:
            count = observer.scalar(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE application_name = :name AND wait_event_type = 'Lock'"
                ),
                {"name": application_name},
            )
        if count == expected:
            return
        time.sleep(0.02)
    pytest.fail(f"Expected {expected} real PostgreSQL lock waiters")


@pytest.mark.parametrize(
    "scenario", ["capacity_join", "cancel_join", "updates", "edit_cancel"]
)
@pytest.mark.parametrize(
    "reverse",
    [False, True],
    ids=["first_operation_wins_lock", "second_operation_wins_lock"],
)
def test_postgres_management_races_obey_both_lock_orders(
    pg_engine, pg_activity, scenario, reverse
):
    activity_id, users = pg_activity
    name = f"dk-manage-{uuid4().hex}"

    def edit(session, values):
        update_activity(
            session, activity_id, users[0], ActivityUpdate.model_validate(values)
        )
        return 200

    def cancel(session):
        cancel_activity(session, activity_id, users[0])
        return 200

    def join(session):
        join_activity(session, activity_id, users[3])
        return 201

    operations = {
        "capacity_join": [lambda session: edit(session, {"max_participants": 2}), join],
        "cancel_join": [cancel, join],
        "updates": [
            lambda session: edit(
                session, {"title": "Organizer update A", "max_participants": 2}
            ),
            lambda session: edit(
                session,
                {
                    "description": "Independent organizer update B.",
                    "max_participants": 4,
                },
            ),
        ],
        "edit_cancel": [
            lambda session: edit(session, {"title": "Organizer update A"}),
            cancel,
        ],
    }[scenario]

    def worker(operation):
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            session.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )
            # Keep a stale ORM instance alive before waiting. The shared locking
            # SELECT must refresh it before validating/merging subsequent writes.
            cached = session.get(Activity, activity_id)
            assert cached is not None
            try:
                return operation(session), None
            except (ActivityManagementError, ParticipationError) as exc:
                return exc.status_code, str(exc)

    # Start workers in a controlled order while holding the activity lock, and
    # observe each waiter before releasing it. Both lock orders are tested.
    order = [1, 0] if reverse else [0, 1]
    futures = {}
    with Session(pg_engine) as holder, ThreadPoolExecutor(max_workers=2) as executor:
        holder.scalar(
            select(Activity).where(Activity.id == activity_id).with_for_update()
        )
        try:
            futures[order[0]] = executor.submit(worker, operations[order[0]])
            wait_for_lock_waiters(pg_engine, name, 1)
            futures[order[1]] = executor.submit(worker, operations[order[1]])
            wait_for_lock_waiters(pg_engine, name, 2)
        finally:
            holder.rollback()
        outcomes = [futures[index].result(timeout=10) for index in (0, 1)]

    with Session(pg_engine) as session:
        result = get_activity_by_id(session, activity_id)
        body = activity_to_read(result)
        count = session.scalar(
            select(func.count())
            .select_from(ActivityParticipation)
            .where(
                ActivityParticipation.activity_id == activity_id,
            )
        )
        assert body.participant_count == count <= body.max_participants
        assert body.available_slots == body.max_participants - count
        if scenario == "capacity_join":
            assert outcomes == (
                [
                    (
                        409,
                        "Participant limit cannot be below current participant count",
                    ),
                    (201, None),
                ]
                if reverse
                else [(200, None), (409, "Activity is full")]
            )
            assert (body.max_participants, count) == ((3, 3) if reverse else (2, 2))
        elif scenario == "cancel_join":
            assert outcomes == (
                [(200, None), (201, None)]
                if reverse
                else [(200, None), (409, "Activity is cancelled")]
            )
            assert body.status == "CANCELLED"
            assert count == (3 if reverse else 2)
        elif scenario == "updates":
            assert outcomes == [(200, None), (200, None)]
            assert body.title == "Organizer update A"
            assert body.description == "Independent organizer update B."
            assert body.max_participants == (2 if reverse else 4)
            assert result.activity.cancelled_at is None
        else:
            assert outcomes == (
                [(409, "Activity is cancelled"), (200, None)]
                if reverse
                else [(200, None), (200, None)]
            )
            assert body.status == "CANCELLED"
            assert body.title == (
                ACTIVITY_CREATE_EXAMPLE["title"] if reverse else "Organizer update A"
            )
