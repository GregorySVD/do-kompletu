from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import test_participation_postgres
from sqlalchemy import delete, event, select, text
from sqlalchemy.orm import Session
from test_activity_management_postgres import wait_for_lock_waiters
from test_lifecycle_worker import DEADLINE, EARLY, OPEN, START

from app.core.config import get_settings
from app.models.activity import Activity
from app.models.activity_participation import (
    CAPACITY_CONSUMING_STATES,
    ActivityParticipation,
)
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCreate
from app.services import activity_management_service as management
from app.services import activity_service as activities
from app.services import participation_lifecycle_service as lifecycle_service
from app.services import participation_service as participation

pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)
pg_engine = test_participation_postgres.pg_engine


@pytest.fixture
def pg_lifecycle(pg_engine, monkeypatch):
    for name, value in {
        "ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE": "60",
        "ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE": "30",
        "ACTIVITY_LATE_CONFIRMATION_GRACE_MINUTES": "10",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    clock = threading.local()
    clock.now = EARLY

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            value = getattr(clock, "now", EARLY)
            return value if tz is not None else value.replace(tzinfo=None)

    for module in (management, activities, participation, lifecycle_service):
        monkeypatch.setattr(module, "datetime", Clock)
    activity_id, user_ids = None, []
    try:
        with Session(pg_engine, expire_on_commit=False) as session:
            suffix = uuid4().hex
            users = [
                User(
                    email=f"auto-{suffix}-{i}@example.com",
                    display_name=f"Auto{suffix}{i}",
                    password_hash="unused",
                )
                for i in range(8)
            ]
            session.add_all(users)
            session.commit()
            user_ids = [user.id for user in users]
            activity_id = activities.create_activity(
                session,
                ActivityCreate.model_validate(
                    {
                        **ACTIVITY_CREATE_EXAMPLE,
                        "start_at": START,
                        "end_at": START + timedelta(hours=2),
                        "min_participants": 2,
                        "max_participants": 2,
                    }
                ),
                users[0],
            ).activity.id
            session.add_all(
                [
                    ActivityParticipation(
                        activity_id=activity_id,
                        user_id=user_ids[1],
                        status="JOINED",
                        joined_at=EARLY,
                    ),
                    ActivityParticipation(
                        activity_id=activity_id,
                        user_id=user_ids[2],
                        status="CONFIRMED",
                        joined_at=EARLY,
                        confirmed_at=OPEN,
                    ),
                ]
            )
            session.add_all(
                [
                    ActivityParticipation(
                        activity_id=activity_id,
                        user_id=user_ids[i],
                        status="WAITLISTED",
                        joined_at=None,
                        waitlisted_at=EARLY + timedelta(seconds=i),
                    )
                    for i in (3, 4, 5)
                ]
            )
            session.commit()
        yield activity_id, user_ids, clock
    finally:
        with pg_engine.begin() as conn:
            if activity_id is not None:
                conn.execute(delete(Activity).where(Activity.id == activity_id))
            if user_ids:
                conn.execute(delete(User).where(User.id.in_(user_ids)))
        get_settings.cache_clear()


def race(engine, activity_id, operations, reverse):
    name = "dk-auto-" + uuid4().hex

    def factory():
        session = Session(engine, expire_on_commit=False, autoflush=False)

        @event.listens_for(session, "after_begin")
        def identify(_session, _transaction, connection):
            connection.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )

        return session

    def worker(operation):
        try:
            return operation(factory)
        except (
            participation.ParticipationError,
            management.ActivityManagementError,
        ) as exc:
            return str(exc)

    order = [1, 0] if reverse else [0, 1]
    futures = {}
    with Session(engine) as holder, ThreadPoolExecutor(max_workers=2) as executor:
        holder.scalar(
            select(Activity).where(Activity.id == activity_id).with_for_update()
        )
        try:
            for expected, index in enumerate(order, 1):
                futures[index] = executor.submit(worker, operations[index])
                wait_for_lock_waiters(engine, name, expected)
        finally:
            holder.rollback()
        return [futures[index].result(timeout=12) for index in (0, 1)]


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize(
    "scenario",
    [
        "confirm_before",
        "confirm_at",
        "leave_before",
        "leave_at",
        "cancel",
        "fifo",
        "multiple",
        "promoted_expires",
        "waiter_leave",
        "at_start",
        "two_workers",
    ],
)
def test_lifecycle_writers_follow_both_real_postgres_lock_orders(
    pg_engine, pg_lifecycle, reverse, scenario
):
    activity_id, users, clock = pg_lifecycle
    sweep_time = START if scenario == "at_start" else DEADLINE
    if scenario == "multiple":
        with Session(pg_engine) as session:
            member = session.get(ActivityParticipation, (activity_id, users[2]))
            member.status = "JOINED"
            member.confirmed_at = None
            session.commit()
    if scenario == "promoted_expires":
        initial = lifecycle_service.run_participation_lifecycle_sweep(
            lambda: Session(pg_engine), now=DEADLINE
        )
        assert initial.confirmation_expired == initial.promoted == 1
        sweep_time = DEADLINE + timedelta(minutes=10)

    def sweep(factory):
        clock.now = sweep_time
        # Candidate and activity transactions are distinct. Factory deliberately
        # marks both connections for observing actual PostgreSQL lock waits.
        return lifecycle_service.run_participation_lifecycle_sweep(factory)

    def request(factory, operation, user=1, now=DEADLINE):
        clock.now = now
        with factory() as session:
            cached = session.get(Activity, activity_id)
            cached_member = session.get(
                ActivityParticipation, (activity_id, users[user])
            )
            assert cached is not None
            if user != 0:
                assert cached_member is not None
            return operation(session, activity_id, users[user])

    if scenario.startswith("confirm"):
        other = lambda factory: request(
            factory,
            participation.confirm_activity,
            now=DEADLINE - timedelta(microseconds=1)
            if scenario == "confirm_before"
            else DEADLINE,
        )
    elif scenario.startswith("leave"):
        other = lambda factory: request(
            factory,
            participation.leave_activity,
            now=DEADLINE - timedelta(microseconds=1)
            if scenario == "leave_before"
            else DEADLINE,
        )
    elif scenario == "cancel":
        other = lambda factory: request(factory, management.cancel_activity, user=0)
    elif scenario == "waiter_leave":
        other = lambda factory: request(factory, participation.leave_activity, user=3)
    else:
        other = sweep
    # First operation is always the sweep; reverse makes the user action win.
    outcomes = race(pg_engine, activity_id, [sweep, other], reverse)
    assert all(
        not isinstance(outcome, lifecycle_service.LifecycleSweepResult)
        or outcome.failed == 0
        for outcome in outcomes
    )
    with Session(pg_engine) as session:
        rows = {
            row.user_id: row
            for row in session.scalars(
                select(ActivityParticipation).where(
                    ActivityParticipation.activity_id == activity_id
                )
            )
        }
        activity = session.get(Activity, activity_id)
        active = [
            row for row in rows.values() if row.status in CAPACITY_CONSUMING_STATES
        ]
        assert len(active) <= activity.max_participants
        if scenario == "cancel" and reverse:
            assert (
                rows[users[1]].status == "JOINED"
                and rows[users[3]].status == "WAITLISTED"
            )
        elif scenario == "confirm_before" and reverse:
            assert (
                rows[users[1]].status == "CONFIRMED"
                and rows[users[3]].status == "WAITLISTED"
            )
        elif scenario == "leave_before" and reverse:
            assert rows[users[1]].status == "LEFT"
            # Promotion one microsecond before normal deadline receives that
            # normal deadline, per the explicit joined_at < deadline rule.
            assert rows[users[3]].status == "CONFIRMATION_EXPIRED"
            assert rows[users[4]].status == "JOINED"
        else:
            assert rows[users[1]].status == "CONFIRMATION_EXPIRED"
            assert rows[users[1]].left_at is None
            if scenario == "at_start":
                assert len(active) == 1
                for user in users[3:6]:
                    assert (
                        rows[user].status == "WAITLIST_EXPIRED"
                        and rows[user].waitlist_expired_at == START
                    )
            elif scenario == "multiple":
                assert rows[users[2]].status == "CONFIRMATION_EXPIRED"
                assert rows[users[3]].status == rows[users[4]].status == "JOINED"
                assert rows[users[5]].status == "WAITLISTED"
            elif scenario in {"promoted_expires", "waiter_leave"}:
                assert rows[users[3]].status == (
                    "CONFIRMATION_EXPIRED" if scenario == "promoted_expires" else "LEFT"
                )
                assert (
                    rows[users[4]].status == "JOINED"
                    and rows[users[5]].status == "WAITLISTED"
                )
            else:
                assert (
                    rows[users[3]].status == "JOINED"
                    and rows[users[4]].status == "WAITLISTED"
                )
        if scenario == "cancel":
            assert activity.cancelled_at is not None
        if scenario in {"confirm_at", "leave_at"}:
            assert isinstance(outcomes[1], str)
        for row in active:
            assert (
                row.confirmation_expired_at is None and row.waitlist_expired_at is None
            )


def test_sweep_refreshes_clock_after_waiting_across_start(
    pg_engine, pg_lifecycle, monkeypatch
):
    activity_id, users, _clock = pg_lifecycle
    current = [DEADLINE]

    class SweepClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return current[0] if tz is not None else current[0].replace(tzinfo=None)

    monkeypatch.setattr(lifecycle_service, "datetime", SweepClock)
    name = "dk-clock-" + uuid4().hex

    def factory():
        session = Session(pg_engine)

        @event.listens_for(session, "after_begin")
        def identify(_session, _transaction, connection):
            connection.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )

        return session

    with Session(pg_engine) as holder, ThreadPoolExecutor(max_workers=1) as executor:
        holder.scalar(
            select(Activity).where(Activity.id == activity_id).with_for_update()
        )
        try:
            future = executor.submit(
                lifecycle_service.run_participation_lifecycle_sweep, factory
            )
            wait_for_lock_waiters(pg_engine, name, 1)
            current[0] = START
        finally:
            holder.rollback()
        result = future.result(timeout=12)
    assert (
        result.confirmation_expired,
        result.promoted,
        result.waitlist_expired,
        result.failed,
    ) == (1, 0, 3, 0)
    with Session(pg_engine) as session:
        expired = session.get(ActivityParticipation, (activity_id, users[1]))
        assert expired.confirmation_expired_at == START
