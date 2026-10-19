from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError
from test_participation_lifecycle import freeze

from app.core.config import Settings, get_settings
from app.core.security import create_access_token
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCreate
from app.services.activity_service import (
    activity_to_read,
    create_activity,
    get_activity_by_id,
)
from app.services.participation_lifecycle_service import (
    run_participation_lifecycle_sweep,
)
from app.services.participation_rules import (
    confirmation_window,
    effective_confirmation_deadline,
)

START = datetime(2030, 8, 8, 18, tzinfo=UTC)
EARLY = START - timedelta(hours=2)
OPEN = START - timedelta(minutes=60)
DEADLINE = START - timedelta(minutes=30)


@pytest.fixture
def lifecycle(db_session, monkeypatch):
    for name, value in {
        "ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE": "60",
        "ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE": "30",
        "ACTIVITY_LATE_CONFIRMATION_GRACE_MINUTES": "10",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    freeze(monkeypatch, EARLY)
    users = [
        User(
            id=UUID(int=i + 1),
            email=f"life{i}@example.com",
            display_name=f"Life{i}",
            password_hash="unused",
        )
        for i in range(10)
    ]
    db_session.add_all(users)
    db_session.commit()
    activity = create_activity(
        db_session,
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
    ).activity
    return activity.id, [user.id for user in users]


def seed(session, context, active=(1, 2), waiters=(3, 4, 5, 6), joined_at=EARLY):
    activity_id, users = context
    for user in active:
        session.add(
            ActivityParticipation(
                activity_id=activity_id,
                user_id=users[user],
                status="JOINED",
                joined_at=joined_at,
            )
        )
    for index, user in enumerate(waiters):
        session.add(
            ActivityParticipation(
                activity_id=activity_id,
                user_id=users[user],
                status="WAITLISTED",
                joined_at=None,
                waitlisted_at=EARLY + timedelta(seconds=index),
            )
        )
    session.commit()


def stored(session, context, user):
    return session.get(
        ActivityParticipation, (context[0], context[1][user]), populate_existing=True
    )


def view(session, context, user, now):
    return activity_to_read(
        get_activity_by_id(
            session, context[0], current_user_id=context[1][user], as_of=now
        )
    )


def headers(context, user):
    return {"Authorization": f"Bearer {create_access_token(context[1][user])}"}


@pytest.mark.parametrize(
    "values",
    [
        {"activity_confirmation_open_minutes_before": 0},
        {
            "activity_confirmation_open_minutes_before": 30,
            "activity_confirmation_deadline_minutes_before": 30,
        },
        {
            "activity_confirmation_open_minutes_before": 20,
            "activity_confirmation_deadline_minutes_before": 30,
        },
        {"activity_confirmation_deadline_minutes_before": -1},
        {"activity_late_confirmation_grace_minutes": 0},
        {"activity_late_confirmation_grace_minutes": -1},
        {"participation_lifecycle_sweep_interval_seconds": 0},
        {"participation_lifecycle_sweep_interval_seconds": -1},
        {"participation_lifecycle_sweep_interval_seconds": float("inf")},
        {"participation_lifecycle_sweep_interval_seconds": float("nan")},
    ],
)
def test_lifecycle_configuration_rejects_invalid_values(values):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite://", **values)


def test_default_window_and_zero_deadline_configuration(lifecycle, monkeypatch):
    assert confirmation_window(START) == (OPEN, DEADLINE)
    monkeypatch.setenv("ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE", "0")
    get_settings.cache_clear()
    assert confirmation_window(START) == (OPEN, START)


@pytest.mark.parametrize(
    "joined,expected",
    [
        (EARLY, DEADLINE),
        (DEADLINE - timedelta(microseconds=1), DEADLINE),
        (DEADLINE, DEADLINE + timedelta(minutes=10)),
        (START - timedelta(minutes=20), START - timedelta(minutes=10)),
        (START - timedelta(minutes=5), START),
    ],
)
def test_effective_deadline_early_equal_late_and_start_cap(lifecycle, joined, expected):
    assert effective_confirmation_deadline(START, joined) == expected


@pytest.mark.parametrize(
    "now,allowed",
    [
        (OPEN - timedelta(seconds=1), False),
        (OPEN, True),
        (DEADLINE - timedelta(microseconds=1), True),
        (DEADLINE, False),
    ],
)
def test_normal_confirmation_exact_boundaries(
    client, db_session, lifecycle, monkeypatch, now, allowed
):
    seed(db_session, lifecycle, active=(1,), waiters=())
    freeze(monkeypatch, now)
    before = view(db_session, lifecycle, 1, now)
    assert before.permissions.can_confirm is allowed
    assert (
        before.current_user_participation.effective_confirmation_deadline_at == DEADLINE
    )
    response = client.post(
        f"/api/v1/activities/{lifecycle[0]}/confirm", headers=headers(lifecycle, 1)
    )
    assert response.status_code == (200 if allowed else 409)


@pytest.mark.parametrize(
    "joined,offset,allowed",
    [
        (DEADLINE, timedelta(minutes=10, microseconds=-1), True),
        (DEADLINE, timedelta(minutes=10), False),
        (START - timedelta(minutes=5), timedelta(minutes=5, microseconds=-1), True),
        (START - timedelta(minutes=5), timedelta(minutes=5), False),
    ],
)
@pytest.mark.parametrize("rejoin", [False, True])
def test_late_direct_join_gets_effective_deadline_without_worker(
    client, db_session, lifecycle, monkeypatch, joined, offset, allowed, rejoin
):
    if rejoin:
        db_session.add(
            ActivityParticipation(
                activity_id=lifecycle[0],
                user_id=lifecycle[1][1],
                status="LEFT",
                joined_at=EARLY,
                left_at=OPEN,
            )
        )
        db_session.commit()
    freeze(monkeypatch, joined)
    response = client.post(
        f"/api/v1/activities/{lifecycle[0]}/join", headers=headers(lifecycle, 1)
    )
    assert response.status_code == 201
    membership = response.json()["current_user_participation"]
    assert datetime.fromisoformat(
        membership["effective_confirmation_deadline_at"]
    ) == min(joined + timedelta(minutes=10), START)
    assert (
        datetime.fromisoformat(response.json()["confirmation_deadline_at"]) == DEADLINE
    )
    freeze(monkeypatch, joined + offset)
    assert (
        view(db_session, lifecycle, 1, joined + offset).permissions.can_confirm
        is allowed
    )
    assert client.post(
        f"/api/v1/activities/{lifecycle[0]}/confirm", headers=headers(lifecycle, 1)
    ).status_code == (200 if allowed else 409)


def test_sweep_without_requests_expires_promotes_multiple_rounds_and_is_idempotent(
    db_session, session_factory, lifecycle
):
    # No TestClient or HTTP endpoint is invoked by this test or fixture.
    seed(db_session, lifecycle)
    before = run_participation_lifecycle_sweep(
        session_factory, now=DEADLINE - timedelta(microseconds=1)
    )
    assert before.confirmation_expired == before.promoted == 0
    first = run_participation_lifecycle_sweep(session_factory, now=DEADLINE)
    assert (
        first.confirmation_expired,
        first.promoted,
        first.waitlist_expired,
        first.failed,
    ) == (2, 2, 0, 0)
    for user in (1, 2):
        expired = stored(db_session, lifecycle, user)
        assert expired.status == "CONFIRMATION_EXPIRED"
        assert expired.confirmation_expired_at.replace(tzinfo=UTC) == DEADLINE
        assert (
            expired.joined_at.replace(tzinfo=UTC) == EARLY and expired.left_at is None
        )
    for user in (3, 4):
        promoted = stored(db_session, lifecycle, user)
        assert (
            promoted.status == "JOINED"
            and promoted.joined_at.replace(tzinfo=UTC) == DEADLINE
        )
        assert promoted.waitlisted_at is not None and promoted.confirmed_at is None
        assert (
            view(
                db_session, lifecycle, user, DEADLINE
            ).current_user_participation.effective_confirmation_deadline_at
            == DEADLINE + timedelta(minutes=10)
        )
    repeat = run_participation_lifecycle_sweep(session_factory, now=DEADLINE)
    assert repeat.confirmation_expired == repeat.promoted == 0
    second = run_participation_lifecycle_sweep(
        session_factory, now=DEADLINE + timedelta(minutes=10)
    )
    assert second.confirmation_expired == second.promoted == 2
    assert stored(db_session, lifecycle, 3).status == "CONFIRMATION_EXPIRED"
    assert stored(db_session, lifecycle, 5).status == "JOINED"


def test_waitlist_expires_at_start_without_promotion_or_automatic_finalization(
    db_session, session_factory, lifecycle
):
    seed(db_session, lifecycle)
    result = run_participation_lifecycle_sweep(session_factory, now=START)
    assert (result.confirmation_expired, result.promoted, result.waitlist_expired) == (
        2,
        0,
        4,
    )
    own = view(db_session, lifecycle, 3, START)
    assert own.waitlist_count == own.participant_count == 0
    assert own.current_user_participation.status == "WAITLIST_EXPIRED"
    assert own.current_user_participation.waitlist_position is None
    assert own.current_user_participation.joined_at is None
    assert not any(own.permissions.model_dump().values())
    assert own.current_user_participation.waitlist_expired_at == START
    assert stored(db_session, lifecycle, 3).no_show_at is None
    assert (
        run_participation_lifecycle_sweep(session_factory, now=START).waitlist_expired
        == 0
    )
    activity = db_session.get(Activity, lifecycle[0], populate_existing=True)
    assert activity.cancelled_at is None


@pytest.mark.parametrize(
    "status", ["CONFIRMED", "CHECKED_IN", "COMPLETED", "NO_SHOW", "LEFT"]
)
def test_sweep_preserves_non_joined_evidence(
    db_session, session_factory, lifecycle, status
):
    seed(db_session, lifecycle, active=(1,), waiters=())
    member = stored(db_session, lifecycle, 1)
    member.status = status
    if status in {"CONFIRMED", "CHECKED_IN", "COMPLETED"}:
        member.confirmed_at = OPEN
    if status in {"CHECKED_IN", "COMPLETED"}:
        member.checked_in_at = START
    if status == "COMPLETED":
        member.completed_at = START + timedelta(hours=2)
    if status == "NO_SHOW":
        member.no_show_at = START + timedelta(hours=2)
    if status == "LEFT":
        member.left_at = OPEN
    db_session.commit()
    result = run_participation_lifecycle_sweep(
        session_factory, now=START + timedelta(days=1)
    )
    assert result.activities_processed == 0
    assert stored(db_session, lifecycle, 1).status == status


def test_cancelled_activity_is_never_automated(db_session, session_factory, lifecycle):
    seed(db_session, lifecycle)
    activity = db_session.get(Activity, lifecycle[0])
    activity.cancelled_at = OPEN
    db_session.commit()
    result = run_participation_lifecycle_sweep(session_factory, now=START)
    assert (
        result.activities_processed
        == result.confirmation_expired
        == result.promoted
        == result.waitlist_expired
        == 0
    )
    assert stored(db_session, lifecycle, 1).status == "JOINED"
    assert stored(db_session, lifecycle, 3).status == "WAITLISTED"


def test_expired_private_detail_terminal_mutations_and_personal_lists(
    client, db_session, session_factory, lifecycle, monkeypatch
):
    seed(db_session, lifecycle)
    run_participation_lifecycle_sweep(session_factory, now=DEADLINE)
    freeze(monkeypatch, DEADLINE)
    detail = client.get(
        f"/api/v1/activities/{lifecycle[0]}", headers=headers(lifecycle, 1)
    ).json()
    assert detail["current_user_participation"]["status"] == "CONFIRMATION_EXPIRED"
    assert not any(detail["permissions"].values())
    for operation in ("join", "leave", "confirm", "check-in"):
        method = client.delete if operation == "leave" else client.post
        suffix = "join" if operation == "leave" else operation
        kwargs = (
            {"json": {"latitude": 52.4, "longitude": 16.9}}
            if operation == "check-in"
            else {}
        )
        assert (
            method(
                f"/api/v1/activities/{lifecycle[0]}/{suffix}",
                headers=headers(lifecycle, 1),
                **kwargs,
            ).status_code
            == 409
        )
    assert (
        client.get(f"/api/v1/activities/{lifecycle[0]}").json()[
            "current_user_participation"
        ]
        is None
    )
    assert (
        client.get(
            f"/api/v1/activities/{lifecycle[0]}", headers=headers(lifecycle, 9)
        ).json()["current_user_participation"]
        is None
    )
    assert (
        client.get(
            "/api/v1/users/me/activities",
            params={"relation": "joined"},
            headers=headers(lifecycle, 1),
        ).json()
        == []
    )
    run_participation_lifecycle_sweep(session_factory, now=START)
    assert (
        client.get(
            "/api/v1/users/me/activities",
            params={"relation": "waitlisted"},
            headers=headers(lifecycle, 5),
        ).json()
        == []
    )
    # Even artificially restoring future dates must not make either expired state rejoinable.
    for user in (1, 5):
        assert client.post(
            f"/api/v1/activities/{lifecycle[0]}/join", headers=headers(lifecycle, user)
        ).json() == {"detail": "Participation has expired"}


def test_overdue_leave_cannot_bypass_deadline_by_rejoin_without_sweep(
    client, db_session, lifecycle, monkeypatch
):
    seed(db_session, lifecycle, active=(1,), waiters=())
    freeze(monkeypatch, DEADLINE)
    before = view(db_session, lifecycle, 1, DEADLINE)
    assert not before.permissions.can_leave and not before.permissions.can_confirm
    response = client.delete(
        f"/api/v1/activities/{lifecycle[0]}/join", headers=headers(lifecycle, 1)
    )
    assert response.status_code == 409
    assert stored(db_session, lifecycle, 1).status == "JOINED"
    assert (
        client.post(
            f"/api/v1/activities/{lifecycle[0]}/join", headers=headers(lifecycle, 1)
        ).status_code
        == 409
    )


def test_schedule_edit_rederives_deadlines_and_preserves_fifo(
    client, db_session, lifecycle, monkeypatch
):
    seed(db_session, lifecycle)
    freeze(monkeypatch, OPEN)
    before = stored(db_session, lifecycle, 3).waitlisted_at
    result = client.patch(
        f"/api/v1/activities/{lifecycle[0]}",
        headers=headers(lifecycle, 0),
        json={
            "start_at": (START + timedelta(hours=1)).isoformat(),
            "end_at": (START + timedelta(hours=3)).isoformat(),
        },
    )
    assert result.status_code == 200
    own = view(db_session, lifecycle, 1, OPEN)
    assert own.confirmation_deadline_at == DEADLINE + timedelta(hours=1)
    assert (
        own.current_user_participation.effective_confirmation_deadline_at
        == DEADLINE + timedelta(hours=1)
    )
    assert stored(db_session, lifecycle, 3).waitlisted_at == before


@pytest.mark.parametrize(
    "values",
    [
        {"status": "CONFIRMATION_EXPIRED"},
        {
            "status": "CONFIRMATION_EXPIRED",
            "joined_at": None,
            "confirmation_expired_at": DEADLINE,
        },
        {
            "status": "CONFIRMATION_EXPIRED",
            "confirmation_expired_at": DEADLINE,
            "confirmed_at": OPEN,
        },
        {
            "status": "CONFIRMATION_EXPIRED",
            "confirmation_expired_at": DEADLINE,
            "left_at": OPEN,
        },
        {"status": "WAITLIST_EXPIRED", "waitlist_expired_at": START, "joined_at": None},
        {
            "status": "WAITLIST_EXPIRED",
            "waitlisted_at": EARLY,
            "waitlist_expired_at": START,
        },
        {
            "status": "WAITLIST_EXPIRED",
            "waitlisted_at": EARLY,
            "waitlist_expired_at": START,
            "joined_at": None,
            "confirmation_expired_at": START,
        },
        {"confirmation_expired_at": DEADLINE},
        {"waitlist_expired_at": START},
    ],
)
def test_expiry_check_constraints_reject_impossible_evidence(
    db_session, lifecycle, values
):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            ActivityParticipation(
                activity_id=lifecycle[0],
                user_id=lifecycle[1][1],
                **{"status": "JOINED", "joined_at": EARLY, **values},
            )
        )
        db_session.flush()


def test_sweep_rejects_naive_time(session_factory, lifecycle):
    with pytest.raises(ValueError, match="timezone-aware"):
        run_participation_lifecycle_sweep(
            session_factory, now=START.replace(tzinfo=None)
        )


def test_worker_is_disabled_in_normal_tests():
    from app.main import app

    async def scenario():
        async with app.router.lifespan_context(app):
            assert app.state.participation_lifecycle_task is None

    asyncio.run(scenario())


def test_worker_lifespan_starts_once_off_event_loop_and_stops_cleanly(monkeypatch):
    import app.workers.participation_lifecycle as worker
    from app.main import create_app

    monkeypatch.setenv("PARTICIPATION_LIFECYCLE_WORKER_ENABLED", "true")
    get_settings.cache_clear()
    calls = []

    async def scenario():
        loop = asyncio.get_running_loop()
        called = asyncio.Event()

        def sweep(*args):
            calls.append(threading.get_ident())
            loop.call_soon_threadsafe(called.set)

        monkeypatch.setattr(worker, "run_participation_lifecycle_sweep", sweep)
        app = create_app()
        async with app.router.lifespan_context(app):
            await asyncio.wait_for(called.wait(), timeout=2)
            task = app.state.participation_lifecycle_task
            assert task.get_name() == "participation-lifecycle" and not task.done()
            assert calls == [calls[0]] and calls[0] != threading.get_ident()
        assert task.done() and task.exception() is None

    asyncio.run(scenario())


def test_worker_logs_error_and_runs_future_sweep(caplog):
    from app.workers.participation_lifecycle import run_lifecycle_worker

    calls = []

    async def scenario():
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()

        def sweep():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("deliberate sweep failure")
            loop.call_soon_threadsafe(stop.set)

        await asyncio.wait_for(
            run_lifecycle_worker(stop, sweep=sweep, interval_seconds=0.001), timeout=2
        )

    asyncio.run(scenario())
    assert len(calls) == 2 and "deliberate sweep failure" in caplog.text


@pytest.mark.parametrize("extra_joined", [0, 40])
def test_sweep_queries_are_batched_and_read_routes_still_constant(
    db_session, session_factory, lifecycle, extra_joined
):
    seed(db_session, lifecycle)
    db_session.get(Activity, lifecycle[0]).max_participants = 2 + extra_joined
    for index in range(extra_joined):
        person = User(
            email=f"batch{index}@example.com",
            display_name=f"Batch{index}",
            password_hash="unused",
        )
        db_session.add(person)
        db_session.flush()
        db_session.add(
            ActivityParticipation(
                activity_id=lifecycle[0],
                user_id=person.id,
                status="JOINED",
                joined_at=EARLY,
            )
        )
    db_session.commit()
    statements = []

    def record(_conn, _cursor, sql, _params, _context, _many):
        statements.append(sql.lstrip().upper())

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        run_participation_lifecycle_sweep(session_factory, now=DEADLINE)
        assert sum(sql.startswith("SELECT") for sql in statements) == 4
        assert sum(sql.startswith("UPDATE") for sql in statements) == 2
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_failed_activity_rolls_back_and_other_activity_still_processes(
    db_session, session_factory, lifecycle, monkeypatch, caplog
):
    import app.services.participation_lifecycle_service as service

    seed(db_session, lifecycle)
    source = db_session.get(Activity, lifecycle[0])
    other = Activity(
        **{
            column.name: getattr(source, column.name)
            for column in Activity.__table__.columns
            if column.name not in {"id", "created_at", "updated_at"}
        }
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(
        ActivityParticipation(
            activity_id=other.id,
            user_id=lifecycle[1][1],
            status="JOINED",
            joined_at=EARLY,
        )
    )
    db_session.commit()
    original = service.promote_waitlisted_participants

    def fail_one(session, activity, now):
        if activity.id == lifecycle[0]:
            raise RuntimeError("deliberate promotion rollback")
        return original(session, activity, now)

    monkeypatch.setattr(service, "promote_waitlisted_participants", fail_one)
    result = run_participation_lifecycle_sweep(session_factory, now=DEADLINE)
    assert (
        result.failed == 1
        and result.activities_processed == 1
        and result.confirmation_expired == 1
    )
    assert stored(db_session, lifecycle, 1).status == "JOINED"
    assert stored(db_session, lifecycle, 3).status == "WAITLISTED"
    assert (
        db_session.get(
            ActivityParticipation, (other.id, lifecycle[1][1]), populate_existing=True
        ).status
        == "CONFIRMATION_EXPIRED"
    )
    assert "deliberate promotion rollback" in caplog.text


def test_expired_states_are_untouched_by_explicit_finalization(
    client, db_session, session_factory, lifecycle, monkeypatch
):
    seed(db_session, lifecycle)
    run_participation_lifecycle_sweep(session_factory, now=START)
    for user, state in ((7, "CONFIRMED"), (8, "CHECKED_IN")):
        db_session.add(
            ActivityParticipation(
                activity_id=lifecycle[0],
                user_id=lifecycle[1][user],
                status=state,
                joined_at=EARLY,
                confirmed_at=OPEN,
                checked_in_at=START if state == "CHECKED_IN" else None,
            )
        )
    db_session.commit()
    freeze(monkeypatch, START + timedelta(hours=2))
    assert (
        client.post(
            f"/api/v1/activities/{lifecycle[0]}/finalize", headers=headers(lifecycle, 0)
        ).status_code
        == 200
    )
    assert stored(db_session, lifecycle, 1).status == "CONFIRMATION_EXPIRED"
    assert stored(db_session, lifecycle, 3).status == "WAITLIST_EXPIRED"
    assert stored(db_session, lifecycle, 7).status == "NO_SHOW"
    assert stored(db_session, lifecycle, 8).status == "COMPLETED"


def test_shutdown_waits_for_in_flight_synchronous_sweep(monkeypatch):
    import app.workers.participation_lifecycle as worker
    from app.main import create_app

    monkeypatch.setenv("PARTICIPATION_LIFECYCLE_WORKER_ENABLED", "true")
    get_settings.cache_clear()
    release = threading.Event()
    finished = threading.Event()

    async def scenario():
        loop = asyncio.get_running_loop()
        started = asyncio.Event()

        def sweep(*args):
            loop.call_soon_threadsafe(started.set)
            assert release.wait(timeout=2)
            finished.set()

        monkeypatch.setattr(worker, "run_participation_lifecycle_sweep", sweep)
        app = create_app()
        context = app.router.lifespan_context(app)
        await context.__aenter__()
        await asyncio.wait_for(started.wait(), timeout=2)
        closing = asyncio.create_task(context.__aexit__(None, None, None))
        # Yield scheduling, without a wall-clock sleep or waiting a real interval.
        await asyncio.sleep(0)
        assert not closing.done() and not finished.is_set()
        release.set()
        await asyncio.wait_for(closing, timeout=2)
        assert finished.is_set() and app.state.participation_lifecycle_task.done()

    try:
        asyncio.run(scenario())
    finally:
        release.set()
        get_settings.cache_clear()


def test_openapi_documents_effective_deadline_expiry_and_private_examples(client):
    from app.schemas.activity import ActivityRead

    schema = client.get("/openapi.json").json()
    confirm = schema["paths"]["/api/v1/activities/{activity_id}/confirm"]["post"]
    assert "ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE" in confirm["description"]
    assert "effective_confirmation_deadline_at" in confirm["description"]
    assert "CONFIRMATION_EXPIRED" in confirm["description"]
    properties = schema["components"]["schemas"]["ActivityParticipationRead"][
        "properties"
    ]
    assert {
        "effective_confirmation_deadline_at",
        "confirmation_expired_at",
        "waitlist_expired_at",
    } <= properties.keys()
    assert (
        "effective_confirmation_deadline_at"
        not in schema["components"]["schemas"]["ActivityRead"]["properties"]
    )
    examples = schema["paths"]["/api/v1/activities/{activity_id}"]["get"]["responses"][
        "200"
    ]["content"]["application/json"]["examples"]
    for item in examples.values():
        ActivityRead.model_validate(item["value"])
    assert (
        examples["promoted"]["value"]["current_user_participation"][
            "effective_confirmation_deadline_at"
        ]
        == "2030-08-08T15:40:00Z"
    )
    assert (
        examples["confirmation_expired"]["value"]["current_user_participation"][
            "status"
        ]
        == "CONFIRMATION_EXPIRED"
    )
    assert (
        examples["waitlist_expired"]["value"]["current_user_participation"]["status"]
        == "WAITLIST_EXPIRED"
    )
    assert not any("lifecycle" in path for path in schema["paths"])
