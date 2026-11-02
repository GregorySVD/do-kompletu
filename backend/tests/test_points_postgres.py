"""Exactly-once awards under real PostgreSQL row-lock contention."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
import test_activity_finalization_postgres as attendance
from sqlalchemy import delete, event, select, text, update
from sqlalchemy.orm import Session
from test_activity_management_postgres import pg_client, wait_for_lock_waiters

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.services import activity_management_service as management
from app.services.activity_service import _location_value, get_activity_for_update
from app.services.participation_rules import COMPLETED_ACTIVITY_POINTS

pg_engine = attendance.pg_engine
context = attendance.context
pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


@pytest.mark.parametrize("size,initial", [(1, 0), (3, 0), (1, 30)])
def test_two_concurrent_finalize_requests_award_each_winner_once(
    pg_engine, context, size, initial
):
    activity_id, users, _ = context
    winners = [users[3]] if size == 1 else users[1:4]
    with Session(pg_engine) as session:
        session.execute(
            update(ActivityParticipation)
            .where(
                ActivityParticipation.activity_id == activity_id,
                ActivityParticipation.user_id.in_(winners),
            )
            .values(
                status="CHECKED_IN",
                confirmed_at=attendance.START,
                checked_in_at=attendance.START,
            )
        )
        session.execute(
            update(User).where(User.id.in_(winners)).values(points_total=initial)
        )
        session.commit()
    name = f"dk-points-{uuid4().hex}"
    headers = {"Authorization": f"Bearer {create_access_token(users[0])}"}
    with pg_client(pg_engine) as client:

        def tagged_database():
            with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
                session.execute(
                    text("SELECT set_config('application_name', :name, true)"),
                    {"name": name},
                )
                # Deliberately cache pre-lock state; it cannot drive awards.
                cached_participation = session.get(
                    ActivityParticipation, (activity_id, users[3])
                )
                cached_user = session.get(User, users[3])
                assert cached_participation is not None and cached_user is not None
                yield session

        app.dependency_overrides[get_db] = tagged_database
        with (
            Session(pg_engine) as holder,
            ThreadPoolExecutor(max_workers=2) as executor,
        ):
            get_activity_for_update(holder, activity_id)
            futures = []
            try:
                for expected in (1, 2):
                    futures.append(
                        executor.submit(
                            client.post,
                            f"/api/v1/activities/{activity_id}/finalize",
                            headers=headers,
                        )
                    )
                    wait_for_lock_waiters(pg_engine, name, expected)
            finally:
                holder.rollback()
            responses = [future.result(timeout=15) for future in futures]
        assert sorted(r.status_code for r in responses) == [200, 409]
        assert (
            client.post(
                f"/api/v1/activities/{activity_id}/finalize", headers=headers
            ).status_code
            == 409
        )
    with Session(pg_engine) as session:
        points = dict(
            session.execute(
                select(User.id, User.points_total).where(User.id.in_(users))
            ).all()
        )
        assert points == {
            user: initial + COMPLETED_ACTIVITY_POINTS if user in winners else 0
            for user in users
        }
        for user in winners:
            assert (
                session.get(ActivityParticipation, (activity_id, user)).status
                == "COMPLETED"
            )


def test_postgres_failure_after_points_rolls_back_balance_and_attendance(
    pg_engine, context, monkeypatch
):
    activity_id, users, _ = context
    with Session(pg_engine) as session:
        session.execute(update(User).where(User.id == users[3]).values(points_total=30))
        session.commit()
    original = management._snapshot

    def fail(session, *_args):
        assert (
            session.scalar(select(User.points_total).where(User.id == users[3]))
            == 30 + COMPLETED_ACTIVITY_POINTS
        )
        assert (
            session.get(ActivityParticipation, (activity_id, users[3])).status
            == "COMPLETED"
        )
        raise RuntimeError("Injected failure after points update")

    monkeypatch.setattr(management, "_snapshot", fail)
    with (
        Session(pg_engine) as session,
        pytest.raises(RuntimeError, match="after points update"),
    ):
        management.finalize_activity(session, activity_id, users[0])
    with Session(pg_engine) as session:
        row = session.get(ActivityParticipation, (activity_id, users[3]))
        assert row.status == "CHECKED_IN" and row.completed_at is None
        assert session.get(User, users[3]).points_total == 30
        assert (
            session.get(ActivityParticipation, (activity_id, users[1])).status
            == "JOINED"
        )
    monkeypatch.setattr(management, "_snapshot", original)
    with Session(pg_engine) as session:
        management.finalize_activity(session, activity_id, users[0])
    with Session(pg_engine) as session:
        assert (
            session.get(User, users[3]).points_total == 30 + COMPLETED_ACTIVITY_POINTS
        )


def test_concurrent_different_activities_add_to_shared_user_balance(pg_engine, context):
    activity_id, users, _ = context
    other_id = None
    try:
        with Session(pg_engine) as session:
            source = session.get(Activity, activity_id)
            other = Activity(
                **{
                    column.name: getattr(source, column.name)
                    for column in Activity.__table__.columns
                    if column.name not in {"id", "created_at", "updated_at", "location"}
                },
                location=_location_value(
                    session, attendance.AT_VENUE.latitude, attendance.AT_VENUE.longitude
                ),
            )
            session.add(other)
            session.flush()
            other_id = other.id
            session.add(
                ActivityParticipation(
                    activity_id=other_id,
                    user_id=users[3],
                    status="CHECKED_IN",
                    confirmed_at=attendance.START,
                    checked_in_at=attendance.START,
                )
            )
            session.execute(
                update(User).where(User.id == users[3]).values(points_total=30)
            )
            session.commit()
        barrier = threading.Barrier(2)

        def before_points(_conn, _cursor, statement, *_args):
            if statement.lstrip().upper().startswith("UPDATE USERS"):
                barrier.wait(timeout=10)

        def finalize(target):
            with Session(pg_engine) as session:
                management.finalize_activity(session, target, users[0])

        event.listen(pg_engine, "before_cursor_execute", before_points)
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(finalize, target)
                    for target in (activity_id, other_id)
                ]
                for future in futures:
                    future.result(timeout=15)
        finally:
            event.remove(pg_engine, "before_cursor_execute", before_points)
        with Session(pg_engine) as session:
            assert (
                session.get(User, users[3]).points_total
                == 30 + 2 * COMPLETED_ACTIVITY_POINTS
            )
            assert all(
                session.get(ActivityParticipation, (target, users[3])).status
                == "COMPLETED"
                for target in (activity_id, other_id)
            )
    finally:
        if other_id is not None:
            with pg_engine.begin() as connection:
                connection.execute(delete(Activity).where(Activity.id == other_id))
