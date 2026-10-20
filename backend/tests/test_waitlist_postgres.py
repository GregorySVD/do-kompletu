from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest
import test_participation_postgres
from geoalchemy2 import WKTElement
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session
from test_activity_management_postgres import pg_client, wait_for_lock_waiters
from test_participation_lifecycle import freeze
from test_waitlist import NOW, START

from app.core.security import create_access_token
from app.models.activity import Activity
from app.models.activity_participation import (
    CAPACITY_CONSUMING_STATES,
    ActivityParticipation,
)
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCreate
from app.schemas.activity_management import ActivityUpdate
from app.services.activity_management_service import (
    ActivityManagementError,
    cancel_activity,
    finalize_activity,
    update_activity,
)
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

pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)
pg_engine = test_participation_postgres.pg_engine


@pytest.fixture
def pg_queue(pg_engine, monkeypatch):
    freeze(monkeypatch, NOW)
    activity_id, user_ids = None, []
    try:
        with Session(pg_engine, expire_on_commit=False) as session:
            suffix = uuid4().hex
            users = [
                User(
                    email=f"queue-{suffix}-{i}@example.com",
                    display_name=f"Queue{suffix}{i}",
                    password_hash="unused",
                )
                for i in range(9)
            ]
            session.add_all(users)
            session.commit()
            user_ids = [user.id for user in users]
            activity_id = create_activity(
                session,
                ActivityCreate.model_validate(
                    {
                        **ACTIVITY_CREATE_EXAMPLE,
                        "min_participants": 2,
                        "max_participants": 2,
                        "start_at": START,
                        "end_at": START + timedelta(hours=2),
                    }
                ),
                users[0],
            ).activity.id
        yield activity_id, user_ids
    finally:
        with pg_engine.begin() as connection:
            if activity_id is not None:
                connection.execute(delete(Activity).where(Activity.id == activity_id))
            if user_ids:
                connection.execute(delete(User).where(User.id.in_(user_ids)))


def seed(session, activity_id, users, active=(1, 2), waiters=(3, 4, 5)):
    for user in (*active, *waiters):
        join_activity(session, activity_id, users[user])
    for index, user in enumerate(waiters):
        row = session.get(
            ActivityParticipation, (activity_id, users[user]), populate_existing=True
        )
        row.waitlisted_at = NOW - timedelta(seconds=3 - index)
    session.commit()


def race(engine, activity_id, operations, reverse):
    """Queue each writer behind a real parent lock and observe PostgreSQL waiting."""
    name = "dk-waitlist-" + uuid4().hex

    def worker(operation):
        with Session(engine, expire_on_commit=False, autoflush=False) as session:
            session.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )
            # Exercise populate_existing after the writer waited behind a commit.
            cached_activity = session.get(Activity, activity_id)
            cached_rows = list(
                session.scalars(
                    select(ActivityParticipation).where(
                        ActivityParticipation.activity_id == activity_id
                    )
                )
            )
            assert cached_activity is not None and cached_rows
            try:
                result = operation(session)
                return result.current_user_participation_status, None
            except (ParticipationError, ActivityManagementError) as exc:
                return None, str(exc)

    order = list(range(len(operations)))
    if reverse:
        order.reverse()
    with (
        Session(engine) as holder,
        ThreadPoolExecutor(max_workers=len(operations)) as executor,
    ):
        holder.scalar(
            select(Activity).where(Activity.id == activity_id).with_for_update()
        )
        futures = {}
        try:
            for expected, index in enumerate(order, 1):
                futures[index] = executor.submit(worker, operations[index])
                wait_for_lock_waiters(engine, name, expected)
        finally:
            holder.rollback()
        return [futures[index].result(timeout=12) for index in range(len(operations))]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "scenario",
    [
        "last_slot",
        "already_full",
        "leave_promote",
        "two_leaves",
        "waitlist_leave",
        "rejoin",
        "capacity_increase",
        "cancel_leave",
        "cancel_capacity",
    ],
)
def test_waitlist_writers_serialize_without_overbooking_or_post_cancel_promotion(
    pg_engine, pg_queue, reverse, scenario
):
    activity_id, users = pg_queue
    with Session(pg_engine, expire_on_commit=False) as session:
        if scenario in {"last_slot", "rejoin"}:
            seed(session, activity_id, users, active=(1,), waiters=())
            if scenario == "rejoin":
                join_activity(session, activity_id, users[2])
                leave_activity(session, activity_id, users[2])
        elif scenario == "already_full":
            seed(session, activity_id, users, waiters=())
        else:
            seed(session, activity_id, users)

    def join(user):
        return lambda session: join_activity(session, activity_id, users[user])

    def leave(user):
        return lambda session: leave_activity(session, activity_id, users[user])

    def increase(session):
        return update_activity(
            session, activity_id, users[0], ActivityUpdate(max_participants=4)
        )

    def cancel(session):
        return cancel_activity(session, activity_id, users[0])

    operations = {
        "last_slot": [join(2), join(3)],
        "already_full": [join(3), join(4), join(5)],
        "leave_promote": [leave(1), join(6)],
        "two_leaves": [leave(1), leave(2)],
        "waitlist_leave": [leave(3), leave(5)],
        "rejoin": [join(2), join(3)],
        "capacity_increase": [increase, join(6)],
        "cancel_leave": [cancel, leave(1)],
        "cancel_capacity": [cancel, increase],
    }[scenario]
    outcomes = race(pg_engine, activity_id, operations, reverse)
    with Session(pg_engine) as session:
        rows = {
            row.user_id: row
            for row in session.scalars(
                select(ActivityParticipation).where(
                    ActivityParticipation.activity_id == activity_id
                )
            )
        }
        body = activity_to_read(get_activity_by_id(session, activity_id))
        active = [
            row for row in rows.values() if row.status in CAPACITY_CONSUMING_STATES
        ]
        assert len(active) == body.participant_count <= body.max_participants
        assert body.waitlist_count == sum(
            row.status == "WAITLISTED" for row in rows.values()
        )
        if scenario in {"last_slot", "rejoin"}:
            assert outcomes == (
                [("WAITLISTED", None), ("JOINED", None)]
                if reverse
                else [("JOINED", None), ("WAITLISTED", None)]
            )
            assert body.participant_count == 2 and body.waitlist_count == 1
            assert len(rows) == 3
        elif scenario == "already_full":
            assert outcomes == [("WAITLISTED", None)] * 3
            expected = sorted(
                users[3:6]
            )  # Equal controlled timestamps: UUID tie-breaker.
            for position, user in enumerate(expected, 1):
                own = activity_to_read(
                    get_activity_by_id(session, activity_id, current_user_id=user)
                )
                assert own.current_user_participation.waitlist_position == position
        elif scenario in {"leave_promote", "two_leaves", "capacity_increase"}:
            assert all(error is None for _, error in outcomes)
            promoted = 1 if scenario == "leave_promote" else 2
            for index, user in enumerate(users[3:6]):
                assert rows[user].status == (
                    "JOINED" if index < promoted else "WAITLISTED"
                )
                assert rows[user].waitlisted_at == NOW - timedelta(seconds=3 - index)
                if index < promoted:
                    assert rows[user].joined_at == NOW
                    assert (
                        rows[user].confirmed_at is None
                        and rows[user].checked_in_at is None
                    )
            remaining = activity_to_read(
                get_activity_by_id(
                    session, activity_id, current_user_id=users[3 + promoted]
                )
            )
            assert remaining.current_user_participation.waitlist_position == 1
        elif scenario == "waitlist_leave":
            assert all(error is None for _, error in outcomes)
            assert body.participant_count == 2 and body.waitlist_count == 1
            own = activity_to_read(
                get_activity_by_id(session, activity_id, current_user_id=users[4])
            )
            assert own.current_user_participation.waitlist_position == 1
        else:
            assert body.status == "CANCELLED"
            assert outcomes[0][1] is None
            assert outcomes[1][1] == (None if reverse else "Activity is cancelled")
            assert rows[users[3]].status == ("JOINED" if reverse else "WAITLISTED")
            assert body.participant_count == (
                2 if scenario == "cancel_leave" or not reverse else 4
            )


@pytest.mark.parametrize("timezone", ["Asia/Kolkata", "Pacific/Honolulu"])
@pytest.mark.parametrize("size", [1, 15])
def test_postgres_waitlist_counts_positions_privacy_and_constant_queries(
    pg_engine, pg_queue, monkeypatch, timezone, size
):
    activity_id, users = pg_queue
    with Session(pg_engine, expire_on_commit=False) as session:
        seed(session, activity_id, users)
        source = session.get(Activity, activity_id)
        # All additional activities and memberships are removed with their owner
        # after this test (explicit cleanup below, before user FK cleanup).
        extra_ids = []
        for i in range(size - 1):
            clone = Activity(
                **{
                    c.name: getattr(source, c.name)
                    for c in Activity.__table__.columns
                    if c.name not in {"id", "created_at", "updated_at"}
                }
            )
            clone.location = WKTElement("POINT(16.9461 52.4232)", srid=4326)
            session.add(clone)
            session.flush()
            extra_ids.append(clone.id)
            session.add(
                ActivityParticipation(
                    activity_id=clone.id,
                    user_id=users[4],
                    status="WAITLISTED",
                    joined_at=None,
                    waitlisted_at=NOW,
                )
            )
        session.commit()
    statements = []

    def record(_conn, _cursor, statement, _params, _ctx, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    @event.listens_for(pg_engine, "checkout")
    def set_timezone(connection, *_):
        with connection.cursor() as cursor:
            cursor.execute("SET TIME ZONE '" + timezone + "'")

    try:
        with pg_client(pg_engine) as client:
            event.listen(pg_engine, "before_cursor_execute", record)
            headers = {"Authorization": f"Bearer {create_access_token(users[4])}"}
            for url, params, expected in (
                ("/api/v1/activities", {"limit": 100}, 1),
                (f"/api/v1/activities/{activity_id}", {}, 2),
                (
                    "/api/v1/users/me/activities",
                    {"relation": "waitlisted", "limit": 100},
                    2,
                ),
            ):
                statements.clear()
                response = client.get(
                    url, headers=headers if expected == 2 else {}, params=params
                )
                assert response.status_code == 200, response.text
                assert len(statements) == expected
                if "me/activities" in url:
                    assert len(response.json()) == size
                    own = next(
                        item
                        for item in response.json()
                        if item["id"] == str(activity_id)
                    )
                    assert own["current_user_participation"]["waitlist_position"] == 2
                    assert own["current_user_participation"]["waitlisted_at"].endswith(
                        "Z"
                    )
        event.remove(pg_engine, "before_cursor_execute", record)
        freeze(monkeypatch, START + timedelta(hours=2))
        with Session(pg_engine) as session:
            finalize_activity(session, activity_id, users[0])
            waiter = session.get(
                ActivityParticipation, (activity_id, users[4]), populate_existing=True
            )
            assert waiter.status == "WAITLISTED" and waiter.no_show_at is None
    finally:
        if event.contains(pg_engine, "before_cursor_execute", record):
            event.remove(pg_engine, "before_cursor_execute", record)
        event.remove(pg_engine, "checkout", set_timezone)
        with pg_engine.begin() as connection:
            connection.execute(delete(Activity).where(Activity.id.in_(extra_ids)))


def test_postgres_fifo_index_plan_avoids_queue_sort(pg_engine, pg_queue):
    activity_id, users = pg_queue
    # Realistic data volume in a rolled-back transaction. Large timestamp range
    # makes a sequential scan + sort measurably different from a FIFO index scan.
    with pg_engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, display_name, password_hash, is_active, points_total, created_at) "
                    "SELECT md5(:prefix || n::text)::uuid, :prefix || n || '@example.com', :prefix || n, 'unused', true, 0, now() "
                    "FROM generate_series(1, 6000) n"
                ),
                {"prefix": uuid4().hex},
            )
            connection.execute(
                text(
                    "INSERT INTO activity_participations (activity_id, user_id, status, joined_at, waitlisted_at) "
                    "SELECT :activity, id, 'WAITLISTED', NULL, :now + row_number() OVER (ORDER BY id) * interval '1 second' "
                    "FROM users WHERE id NOT IN (SELECT user_id FROM activity_participations WHERE activity_id = :activity) "
                    "AND id <> :organizer LIMIT 6000"
                ),
                {"activity": activity_id, "organizer": users[0], "now": NOW},
            )
            connection.execute(text("ANALYZE activity_participations"))
            query = (
                "SELECT user_id FROM activity_participations WHERE activity_id = :activity "
                "AND status = 'WAITLISTED' ORDER BY waitlisted_at, user_id LIMIT 2"
            )
            plan = connection.scalar(
                text("EXPLAIN (FORMAT JSON) " + query), {"activity": activity_id}
            )[0]["Plan"]
            assert "ix_activity_participations_fifo" in str(plan)
            assert "Sort" not in str(plan)
        finally:
            transaction.rollback()
