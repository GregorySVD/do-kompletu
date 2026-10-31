from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, event, select, text
from sqlalchemy.orm import Session
from test_activity_management_postgres import pg_client, wait_for_lock_waiters

from app.core.security import create_access_token
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCreate
from app.schemas.activity_check_in import ActivityCheckIn
from app.schemas.my_activities import ActivityRelation, ActivityScope
from app.services import activity_management_service as management
from app.services import activity_service as activities
from app.services import participation_service as participation
from app.services.participation_rules import COMPLETED_ACTIVITY_POINTS

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    POSTGRES_TEST_DATABASE_URL is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)
END = datetime(2030, 8, 8, 18, tzinfo=UTC)
START = END - timedelta(minutes=15)
AT_VENUE = ActivityCheckIn(latitude=52.4232, longitude=16.9461, accuracy_m=20)


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
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def context(pg_engine, monkeypatch):
    clock = threading.local()
    clock.now = START - timedelta(minutes=1)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            now = getattr(clock, "now", END)
            return now if tz is not None else now.replace(tzinfo=None)

    for module in (management, activities, participation):
        monkeypatch.setattr(module, "datetime", Clock)
    activity_id, users = None, []
    try:
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            suffix = uuid4().hex
            people = [
                User(
                    email=f"final-{suffix}-{i}@example.com",
                    display_name=f"Final{suffix}{i}",
                    password_hash="unused",
                )
                for i in range(6)
            ]
            session.add_all(people)
            session.commit()
            users = [user.id for user in people]
            activity_id = activities.create_activity(
                session,
                ActivityCreate.model_validate(
                    {
                        **ACTIVITY_CREATE_EXAMPLE,
                        "start_at": START,
                        "end_at": END,
                        "min_participants": 2,
                        "max_participants": 6,
                    }
                ),
                people[0],
            ).activity.id
            for user in users[1:5]:
                participation.join_activity(session, activity_id, user)
            for user in users[2:4]:
                participation.confirm_activity(session, activity_id, user)
            participation.check_in_activity(session, activity_id, users[3], AT_VENUE)
            participation.leave_activity(session, activity_id, users[4])
        clock.now = END
        yield activity_id, users, clock
    finally:
        with pg_engine.begin() as connection:
            if activity_id is not None:
                connection.execute(delete(Activity).where(Activity.id == activity_id))
            if users:
                connection.execute(delete(User).where(User.id.in_(users)))


@pytest.mark.parametrize(
    "scenario", ["check_in", "finalize", "cancel", "join", "leave", "confirm"]
)
@pytest.mark.parametrize(
    "reverse", [False, True], ids=["finalize_first", "other_first"]
)
def test_finalization_races_respect_both_lock_orders_at_end(
    pg_engine, context, scenario, reverse
):
    activity_id, users, clock = context

    def finalize(session):
        management.finalize_activity(session, activity_id, users[0])
        return 200

    def check_in(session):
        participation.check_in_activity(session, activity_id, users[2], AT_VENUE)
        return 200

    def cancel(session):
        management.cancel_activity(session, activity_id, users[0])
        return 200

    def join(session):
        participation.join_activity(session, activity_id, users[5])
        return 201

    def leave(session):
        participation.leave_activity(session, activity_id, users[1])
        return 200

    def confirm(session):
        participation.confirm_activity(session, activity_id, users[1])
        return 200

    operations = [
        finalize,
        {
            "check_in": check_in,
            "finalize": finalize,
            "cancel": cancel,
            "join": join,
            "leave": leave,
            "confirm": confirm,
        }[scenario],
    ]
    name = f"dk-finalization-{uuid4().hex}"

    def worker(index):
        # Controlled UTC times follow the observed serialization order; no sleeps
        # are used to cross the activity boundary.
        clock.now = (
            END - timedelta(microseconds=1)
            if index == 1 and reverse and scenario != "finalize"
            else END
        )
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            session.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )
            cached_activity = session.get(Activity, activity_id)
            cached_member = session.get(ActivityParticipation, (activity_id, users[2]))
            assert cached_activity is not None and cached_member is not None
            try:
                return operations[index](session), None
            except (
                management.ActivityManagementError,
                participation.ParticipationError,
            ) as exc:
                return exc.status_code, str(exc)

    order = [1, 0] if reverse else [0, 1]
    futures = {}
    with Session(pg_engine) as holder, ThreadPoolExecutor(max_workers=2) as executor:
        holder.scalar(
            select(Activity).where(Activity.id == activity_id).with_for_update()
        )
        try:
            for expected, index in enumerate(order, 1):
                futures[index] = executor.submit(worker, index)
                wait_for_lock_waiters(pg_engine, name, expected)
        finally:
            holder.rollback()
        outcomes = [futures[i].result(timeout=12) for i in (0, 1)]
    with Session(pg_engine) as session:
        body = activities.activity_to_read(
            activities.get_activity_by_id(session, activity_id)
        )
        rows = {
            row.user_id: row
            for row in session.scalars(
                select(ActivityParticipation).where(
                    ActivityParticipation.activity_id == activity_id
                )
            )
        }
        if scenario == "cancel" and reverse:
            assert outcomes == [(409, "Activity is cancelled"), (200, None)]
            assert (
                body.status == "CANCELLED"
                and body.participant_count == 3
                and body.checked_in_count == 1
            )
            assert (
                rows[users[2]].status == "CONFIRMED"
                and rows[users[3]].status == "CHECKED_IN"
            )
            assert all(
                row.completed_at is None and row.no_show_at is None
                for row in rows.values()
            )
            return
        assert outcomes[0] == (
            (409, "No unresolved attendance to finalize")
            if scenario == "finalize" and reverse
            else (200, None)
        )
        assert body.status == "ENDED" and body.participant_count == 0
        assert rows[users[3]].status == "COMPLETED" and rows[users[4]].status == "LEFT"
        assert rows[users[3]].completed_at == END
        if scenario == "check_in":
            assert outcomes[1] == (
                (200, None) if reverse else (409, "Activity has ended")
            )
            assert rows[users[2]].status == ("COMPLETED" if reverse else "NO_SHOW")
            assert body.checked_in_count == (2 if reverse else 1)
        elif scenario == "finalize":
            assert (
                outcomes.count((200, None))
                == outcomes.count((409, "No unresolved attendance to finalize"))
                == 1
            )
        elif scenario == "cancel":
            assert outcomes[1] == (409, "Activity has ended")
        elif scenario == "join":
            assert outcomes[1] == (
                (409, "Activity has started")
                if reverse
                else (409, "Activity has ended")
            )
            assert users[5] not in rows
        elif scenario == "leave":
            assert outcomes[1] == (
                (409, "Confirmation window has closed")
                if reverse
                else (409, "Attendance outcome is final")
            )
            assert rows[users[1]].status == "NO_SHOW"
        else:
            assert outcomes[1][0] == 409
            assert rows[users[1]].status == "NO_SHOW"


@pytest.mark.parametrize("size", [1, 120])
@pytest.mark.parametrize("status", ["JOINED", "CHECKED_IN"])
def test_postgres_finalization_uses_one_atomic_update_and_constant_http_selects(
    pg_engine, context, size, status
):
    activity_id, users, _ = context
    extras = []
    try:
        with Session(pg_engine) as session:
            session.get(Activity, activity_id).max_participants = None
            session.execute(
                delete(ActivityParticipation).where(
                    ActivityParticipation.activity_id == activity_id
                )
            )
            suffix = uuid4().hex
            people = [
                User(
                    email=f"final-bulk-{suffix}-{i}@example.com",
                    display_name=f"FinalBulk{suffix}{i}",
                    password_hash="unused",
                )
                for i in range(size)
            ]
            session.add_all(people)
            session.flush()
            extras = [user.id for user in people]
            session.add_all(
                [
                    ActivityParticipation(
                        activity_id=activity_id, user_id=user, status=status,
                        confirmed_at=START if status == "CHECKED_IN" else None,
                        checked_in_at=START if status == "CHECKED_IN" else None,
                    )
                    for user in extras
                ]
            )
            session.commit()
        statements = []

        def record(_conn, _cursor, statement, _params, _context, _many):
            statements.append(statement.lstrip().upper())

        with pg_client(pg_engine) as client:
            event.listen(pg_engine, "before_cursor_execute", record)
            try:
                response = client.post(
                    f"/api/v1/activities/{activity_id}/finalize",
                    headers={
                        "Authorization": f"Bearer {create_access_token(users[0])}"
                    },
                )
                assert response.status_code == 200
                assert sum(s.startswith("SELECT") for s in statements) == 3
                assert (
                    sum(
                        s.startswith("UPDATE ACTIVITY_PARTICIPATIONS")
                        for s in statements
                    )
                    == 1
                )
                assert response.json()["participant_count"] == 0
                assert response.json()["available_slots"] is None
                assert sum(s.startswith("UPDATE USERS") for s in statements) == (
                    1 if status == "CHECKED_IN" else 0
                )
            finally:
                event.remove(pg_engine, "before_cursor_execute", record)
        with Session(pg_engine) as session:
            assert all(
                (row.status == "NO_SHOW" and row.no_show_at == END)
                if status == "JOINED" else
                (row.status == "COMPLETED" and row.completed_at == END)
                for row in session.scalars(
                    select(ActivityParticipation).where(
                        ActivityParticipation.activity_id == activity_id
                    )
                )
            )
            assert set(session.scalars(select(User.points_total).where(User.id.in_(extras)))) == {
                COMPLETED_ACTIVITY_POINTS if status == "CHECKED_IN" else 0
            }
    finally:
        if extras:
            with pg_engine.begin() as connection:
                connection.execute(delete(User).where(User.id.in_(extras)))


@pytest.mark.parametrize("zone", ["Asia/Kolkata", "Pacific/Honolulu"])
def test_postgres_final_history_timestamps_privacy_and_counts_across_timezones(
    pg_engine, context, zone
):
    activity_id, users, _ = context
    with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
        session.execute(
            text("SELECT set_config('TimeZone', :zone, true)"), {"zone": zone}
        )
        management.finalize_activity(session, activity_id, users[0])
        session.execute(
            text("SELECT set_config('TimeZone', :zone, true)"), {"zone": zone}
        )
        for user, expected in [
            (users[1], "NO_SHOW"),
            (users[2], "NO_SHOW"),
            (users[3], "COMPLETED"),
        ]:
            body = activities.activity_to_read(
                activities.get_activity_by_id(
                    session, activity_id, current_user_id=user
                )
            )
            assert body.current_user_participation.status == expected
            timestamp = (
                body.current_user_participation.completed_at
                if expected == "COMPLETED"
                else body.current_user_participation.no_show_at
            )
            assert timestamp == END and timestamp.utcoffset() == timedelta(0)
            history = activities.list_user_activities(
                session,
                current_user_id=user,
                relation=ActivityRelation.JOINED,
                scope=ActivityScope.HISTORY,
                limit=100,
                offset=0,
            )
            assert len(history) == 1 and history[0].activity.id == activity_id
            assert (
                history[0].participant_count == 0 and history[0].checked_in_count == 1
            )
            assert (
                activities.list_user_activities(
                    session,
                    current_user_id=user,
                    relation=ActivityRelation.JOINED,
                    scope=ActivityScope.UPCOMING,
                    limit=100,
                    offset=0,
                )
                == []
            )
        assert (
            activities.activity_to_read(
                activities.get_activity_by_id(session, activity_id)
            ).current_user_participation
            is None
        )
        assert (
            activities.list_user_activities(
                session,
                current_user_id=users[4],
                relation=ActivityRelation.JOINED,
                scope=ActivityScope.HISTORY,
                limit=20,
                offset=0,
            )
            == []
        )
