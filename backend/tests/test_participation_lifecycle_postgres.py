from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, event, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_activity_management_postgres import (
    pg_client,
    wait_for_lock_waiters,
)

from app.core.config import get_settings
from app.models.activity import Activity
from app.models.activity_participation import (
    ACTIVE_PARTICIPATION_STATUSES,
    ActivityParticipation,
)
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
from app.services.participation_service import (
    ParticipationError,
    confirm_activity,
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
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def lifecycle_activity(pg_engine, monkeypatch):
    monkeypatch.setenv("ACTIVITY_CONFIRMATION_WINDOW_HOURS", "24")
    get_settings.cache_clear()
    start = datetime.now(UTC) + timedelta(hours=12)
    activity_id = None
    user_ids = []
    try:
        with Session(pg_engine, expire_on_commit=False) as session:
            suffix = uuid4().hex
            users = [
                User(
                    email=f"lifecycle-{suffix}-{i}@example.com",
                    display_name=f"Lifecycle{suffix}{i}",
                    password_hash="unused",
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
                        "start_at": start,
                        "end_at": start + timedelta(hours=2),
                        "min_participants": 2,
                        "max_participants": 3,
                    }
                ),
                users[0],
            )
            activity_id = result.activity.id
            for user in user_ids[1:3]:
                join_activity(session, activity_id, user)
        yield activity_id, user_ids, start
    finally:
        with pg_engine.begin() as connection:
            if activity_id is not None:
                connection.execute(delete(Activity).where(Activity.id == activity_id))
            if user_ids:
                connection.execute(delete(User).where(User.id.in_(user_ids)))
        get_settings.cache_clear()


@pytest.mark.parametrize(
    "scenario",
    [
        "final_slot",
        "leave_join",
        "rejoin_join",
        "confirm_leave",
        "confirm_cancel",
        "confirm_edit",
        "capacity_rejoin",
        "double_confirm",
    ],
)
@pytest.mark.parametrize(
    "reverse", [False, True], ids=["first_waits_first", "second_waits_first"]
)
def test_lifecycle_writers_obey_both_postgres_lock_orders(
    pg_engine, lifecycle_activity, scenario, reverse
):
    activity_id, users, start = lifecycle_activity
    with Session(pg_engine, expire_on_commit=False) as session:
        if scenario in {"leave_join", "rejoin_join", "capacity_rejoin"}:
            join_activity(session, activity_id, users[3])
        if scenario in {"rejoin_join", "capacity_rejoin"}:
            leave_activity(session, activity_id, users[3])
        if scenario == "capacity_rejoin":
            confirm_activity(session, activity_id, users[1])

    def join(session, user):
        join_activity(session, activity_id, users[user])
        return 201

    def leave(session):
        leave_activity(session, activity_id, users[1])
        return 200

    def confirm(session):
        confirm_activity(session, activity_id, users[1])
        return 200

    def cancel(session):
        cancel_activity(session, activity_id, users[0])
        return 200

    def edit(session, values):
        update_activity(
            session, activity_id, users[0], ActivityUpdate.model_validate(values)
        )
        return 200

    operations = {
        "final_slot": [
            lambda session: join(session, 3),
            lambda session: join(session, 4),
        ],
        "leave_join": [leave, lambda session: join(session, 4)],
        "rejoin_join": [
            lambda session: join(session, 3),
            lambda session: join(session, 4),
        ],
        "confirm_leave": [confirm, leave],
        "confirm_cancel": [confirm, cancel],
        "confirm_edit": [
            confirm,
            lambda session: edit(
                session,
                {
                    "start_at": (start + timedelta(days=2)).isoformat(),
                    "end_at": (start + timedelta(days=2, hours=2)).isoformat(),
                },
            ),
        ],
        "capacity_rejoin": [
            lambda session: edit(session, {"max_participants": 2}),
            lambda session: join(session, 3),
        ],
        "double_confirm": [confirm, confirm],
    }[scenario]
    name = f"dk-lifecycle-{uuid4().hex}"

    def worker(operation):
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            session.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )
            # Both the activity and membership may be stale before waiting.
            cached_activity = session.get(Activity, activity_id)
            cached_participation = session.get(
                ActivityParticipation, (activity_id, users[1])
            )
            assert cached_activity is not None and cached_participation is not None
            try:
                return operation(session), None
            except (ParticipationError, ActivityManagementError) as exc:
                return exc.status_code, str(exc)

    order = [1, 0] if reverse else [0, 1]
    futures = {}
    with Session(pg_engine) as holder, ThreadPoolExecutor(max_workers=2) as executor:
        holder.scalar(
            select(Activity).where(Activity.id == activity_id).with_for_update()
        )
        try:
            for expected, index in enumerate(order, 1):
                futures[index] = executor.submit(worker, operations[index])
                wait_for_lock_waiters(pg_engine, name, expected)
        finally:
            holder.rollback()
        outcomes = [futures[index].result(timeout=12) for index in (0, 1)]

    with Session(pg_engine) as session:
        body = activity_to_read(
            get_activity_by_id(session, activity_id, current_user_id=users[1])
        )
        rows = list(
            session.scalars(
                select(ActivityParticipation).where(
                    ActivityParticipation.activity_id == activity_id
                )
            )
        )
        active = [row for row in rows if row.status in ACTIVE_PARTICIPATION_STATUSES]
        assert body.participant_count == len(active) <= body.max_participants
        assert body.available_slots == body.max_participants - len(active)
        member = session.get(ActivityParticipation, (activity_id, users[1]))
        for row in rows:
            assert (row.left_at is not None) is (row.status == "LEFT")
            if row.status == "CONFIRMED":
                assert row.confirmed_at is not None
        if scenario in {"final_slot", "rejoin_join"}:
            assert outcomes.count((201, None)) == 2
            assert len(active) == 3
            if scenario == "rejoin_join":
                rejoined = session.get(ActivityParticipation, (activity_id, users[3]))
                assert rejoined.status == ("WAITLISTED" if reverse else "JOINED")
                assert len(rows) == 4
        elif scenario == "leave_join":
            assert outcomes == [(200, None), (201, None)]
            assert member.status == "LEFT" and len(active) == 3
        elif scenario == "confirm_leave":
            assert outcomes == (
                [(409, "Not participating in this activity"), (200, None)]
                if reverse
                else [(200, None), (200, None)]
            )
            assert member.status == "LEFT" and (member.confirmed_at is None) is reverse
            assert body.current_user_participation is None
            assert (
                body.permissions.can_join
                and not body.permissions.can_confirm
                and not body.permissions.can_leave
            )
        elif scenario == "confirm_cancel":
            assert outcomes == (
                [(409, "Activity is cancelled"), (200, None)]
                if reverse
                else [(200, None), (200, None)]
            )
            assert body.status == "CANCELLED" and not any(
                body.permissions.model_dump().values()
            )
            assert member.status == ("JOINED" if reverse else "CONFIRMED")
        elif scenario == "confirm_edit":
            assert outcomes == (
                [(409, "Confirmation window has not opened"), (200, None)]
                if reverse
                else [
                    (200, None),
                    (409, "Cannot change schedule while participants are confirmed"),
                ]
            )
            assert body.start_at == (start + timedelta(days=2) if reverse else start)
            assert member.status == ("JOINED" if reverse else "CONFIRMED")
        elif scenario == "capacity_rejoin":
            assert outcomes == (
                [
                    (
                        409,
                        "Participant limit cannot be below current participant count",
                    ),
                    (201, None),
                ]
                if reverse
                else [(200, None), (201, None)]
            )
            assert member.status == "CONFIRMED"
            assert (body.max_participants, len(active)) == (
                (3, 3) if reverse else (2, 2)
            )
        else:
            assert outcomes.count((200, None)) == 1
            assert outcomes.count((409, "Already confirmed attendance")) == 1
            assert member.status == "CONFIRMED"


def test_postgres_retained_states_http_counts_privacy_and_query_counts(
    pg_engine, lifecycle_activity
):
    from app.core.security import create_access_token

    activity_id, users, _ = lifecycle_activity
    with Session(pg_engine) as session:
        confirm_activity(session, activity_id, users[1])
        leave_activity(session, activity_id, users[2])
    headers = {"Authorization": f"Bearer {create_access_token(users[1])}"}
    base = f"/api/v1/activities/{activity_id}"
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    with pg_client(pg_engine) as client:
        event.listen(pg_engine, "before_cursor_execute", record)
        try:
            for endpoint, params, authentication, expected in [
                ("/api/v1/activities", {}, {}, 1),
                (base, {}, headers, 2),
                ("/api/v1/users/me/activities", {"relation": "joined"}, headers, 2),
            ]:
                statements.clear()
                response = client.get(endpoint, params=params, headers=authentication)
                assert response.status_code == 200
                assert len(statements) == expected
            body = client.get(base, headers=headers).json()
            assert body["participant_count"] == 1 and body["available_slots"] == 2
            assert body["current_user_participation"]["status"] == "CONFIRMED"
            assert body["current_user_participation"]["confirmed_at"] is not None
            assert client.get(base).json()["current_user_participation"] is None
            left_headers = {"Authorization": f"Bearer {create_access_token(users[2])}"}
            assert (
                client.get(base, headers=left_headers).json()[
                    "current_user_participation"
                ]
                is None
            )
            assert (
                client.get(
                    "/api/v1/users/me/activities",
                    params={"relation": "joined"},
                    headers=left_headers,
                ).json()
                == []
            )
        finally:
            event.remove(pg_engine, "before_cursor_execute", record)


@pytest.mark.parametrize(
    "values",
    [
        {"status": "INVALID"},
        {"status": "CONFIRMED"},
        {"status": "LEFT"},
        {"status": "JOINED", "confirmed_at": datetime.now(UTC)},
    ],
)
def test_postgres_enforces_lifecycle_check_constraints(
    pg_engine, lifecycle_activity, values
):
    activity_id, users, _ = lifecycle_activity
    with Session(pg_engine) as session:
        with pytest.raises(IntegrityError) as caught, session.begin_nested():
            session.add(
                ActivityParticipation(
                    activity_id=activity_id, user_id=users[4], **values
                )
            )
            session.flush()
        assert caught.value.orig.sqlstate == "23514"
        assert caught.value.orig.diag.constraint_name in {
            "ck_activity_participations_status",
            "ck_activity_participations_state_timestamps",
        }


def test_postgres_confirmed_capacity_reduction_ignores_left_rows(
    pg_engine, lifecycle_activity
):
    activity_id, users, _ = lifecycle_activity
    with Session(pg_engine) as session:
        confirm_activity(session, activity_id, users[1])
        join_activity(session, activity_id, users[3])
        with pytest.raises(ActivityManagementError, match="below current"):
            update_activity(
                session, activity_id, users[0], ActivityUpdate(max_participants=2)
            )
        leave_activity(session, activity_id, users[3])
        result = update_activity(
            session, activity_id, users[0], ActivityUpdate(max_participants=2)
        )
        assert result.participant_count == 2
        assert (
            session.scalar(
                select(func.count())
                .select_from(ActivityParticipation)
                .where(ActivityParticipation.activity_id == activity_id)
            )
            == 3
        )


@pytest.mark.parametrize("zone", ["Asia/Kolkata", "Pacific/Honolulu"])
def test_postgres_confirmation_metadata_is_utc_with_constant_select_count(
    pg_engine, lifecycle_activity, zone
):
    activity_id, users, start = lifecycle_activity
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
        session.execute(
            text("SELECT set_config('TimeZone', :zone, true)"), {"zone": zone}
        )
        event.listen(pg_engine, "before_cursor_execute", record)
        try:
            body = activity_to_read(confirm_activity(session, activity_id, users[1]))
            assert (
                len(statements) == 3
            )  # Lock, membership, response projection; HTTP adds auth.
        finally:
            event.remove(pg_engine, "before_cursor_execute", record)
        assert body.confirmation_opens_at == start - timedelta(hours=24)
        assert body.confirmation_deadline_at == start
        assert body.confirmation_opens_at.utcoffset() == timedelta(0)
        assert body.current_user_participation.confirmed_at.utcoffset() == timedelta(0)
