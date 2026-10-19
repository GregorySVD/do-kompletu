from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from geoalchemy2 import Geometry
from sqlalchemy import cast, create_engine, delete, event, func, select, text
from sqlalchemy.orm import Session
from test_activity_management_postgres import pg_client, wait_for_lock_waiters

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.activity import Activity
from app.models.activity_participation import (
    ACTIVE_PARTICIPATION_STATUSES,
    ActivityParticipation,
)
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCreate
from app.schemas.activity_check_in import ActivityCheckIn
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
    check_in_activity,
    confirm_activity,
    join_activity,
    leave_activity,
)

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    POSTGRES_TEST_DATABASE_URL is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)
AT_VENUE = ActivityCheckIn(latitude=52.4232, longitude=16.9461)


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
    for key, value in {
        "ACTIVITY_CHECK_IN_OPEN_MINUTES_BEFORE": "30",
        "ACTIVITY_CHECK_IN_CLOSE_MINUTES_AFTER": "60",
        "ACTIVITY_CHECK_IN_RADIUS_METERS": "150",
        "ACTIVITY_CONFIRMATION_WINDOW_HOURS": "24",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    activity_id = None
    user_ids = []
    start = datetime.now(UTC) + timedelta(minutes=15)
    try:
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            suffix = uuid4().hex
            users = [
                User(
                    email=f"checkin-{suffix}-{i}@example.com",
                    display_name=f"Checkin{suffix}{i}",
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
                        "max_participants": 4,
                    }
                ),
                users[0],
            )
            activity_id = result.activity.id
            join_activity(session, activity_id, user_ids[1])
            confirm_activity(session, activity_id, user_ids[1])
        yield activity_id, user_ids, start
    finally:
        with pg_engine.begin() as connection:
            if activity_id is not None:
                connection.execute(delete(Activity).where(Activity.id == activity_id))
            if user_ids:
                connection.execute(delete(User).where(User.id.in_(user_ids)))
        get_settings.cache_clear()


def projected_coordinates(session, activity_id, distance):
    # Real spheroidal geodesic coordinates, never a degrees-to-meters estimate.
    point = cast(
        func.ST_Project(Activity.location, distance, func.radians(90)),
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
    )
    latitude, longitude = session.execute(
        select(func.ST_Y(point), func.ST_X(point)).where(Activity.id == activity_id)
    ).one()
    return {"latitude": latitude, "longitude": longitude}


@pytest.mark.parametrize(
    "distance,accepted",
    [
        (0, True),
        (50, True),
        (149.99, True),
        (150.01, False),
        (1000, False),
        (100000, False),
    ],
)
def test_postgis_geodesic_radius_inside_and_near_boundary(
    pg_engine, context, distance, accepted
):
    activity_id, users, _ = context
    with Session(pg_engine) as session:
        payload = projected_coordinates(session, activity_id, distance)
    with pg_client(pg_engine) as client:
        response = client.post(
            f"/api/v1/activities/{activity_id}/check-in",
            headers={"Authorization": f"Bearer {create_access_token(users[1])}"},
            json=payload,
        )
        assert response.status_code == (200 if accepted else 409)
        if accepted:
            assert (
                response.json()["current_user_participation"]["status"] == "CHECKED_IN"
            )
            assert response.json()["checked_in_count"] == 1
        else:
            assert response.json() == {"detail": "Outside check-in radius"}
    with Session(pg_engine) as session:
        row = session.get(ActivityParticipation, (activity_id, users[1]))
        assert row.status == ("CHECKED_IN" if accepted else "CONFIRMED")
        assert (row.checked_in_at is not None) is accepted


def test_postgis_longitude_latitude_order_is_not_interchangeable(pg_engine, context):
    activity_id, users, _ = context
    with Session(pg_engine, expire_on_commit=False) as session:
        with pytest.raises(ParticipationError, match="Outside check-in radius"):
            check_in_activity(
                session,
                activity_id,
                users[1],
                ActivityCheckIn(
                    latitude=AT_VENUE.longitude, longitude=AT_VENUE.latitude
                ),
            )
        assert (
            check_in_activity(session, activity_id, users[1], AT_VENUE).checked_in_count
            == 1
        )


def test_postgis_geography_handles_antimeridian(pg_engine, context):
    activity_id, users, _ = context
    with Session(pg_engine, expire_on_commit=False) as session:
        update_activity(
            session,
            activity_id,
            users[0],
            ActivityUpdate(latitude=0, longitude=179.9999),
        )
        body = activity_to_read(
            check_in_activity(
                session,
                activity_id,
                users[1],
                ActivityCheckIn(latitude=0, longitude=-179.9999),
            )
        )
        assert body.checked_in_count == 1  # About 22 meters across the date line.


@pytest.mark.parametrize(
    "scenario", ["duplicate", "leave", "cancel", "location", "time", "confirm"]
)
@pytest.mark.parametrize(
    "reverse", [False, True], ids=["check_in_first", "other_first"]
)
def test_check_in_races_serialize_both_lock_orders(
    pg_engine, context, scenario, reverse
):
    activity_id, users, start = context
    if scenario == "confirm":
        with Session(pg_engine) as session:
            member = session.get(ActivityParticipation, (activity_id, users[1]))
            member.status, member.confirmed_at = "JOINED", None
            session.commit()

    def check(session):
        check_in_activity(session, activity_id, users[1], AT_VENUE)
        return 200

    def leave(session):
        leave_activity(session, activity_id, users[1])
        return 200

    def cancel(session):
        cancel_activity(session, activity_id, users[0])
        return 200

    def edit(session, payload):
        update_activity(
            session, activity_id, users[0], ActivityUpdate.model_validate(payload)
        )
        return 200

    def confirm(session):
        confirm_activity(session, activity_id, users[1])
        return 200

    other = {
        "duplicate": check,
        "leave": leave,
        "cancel": cancel,
        "location": lambda session: edit(session, {"latitude": 50}),
        "time": lambda session: edit(
            session, {"start_at": start + timedelta(minutes=5)}
        ),
        "confirm": confirm,
    }[scenario]
    operations = [check, other]
    name = f"dk-checkin-{uuid4().hex}"

    def worker(operation):
        with Session(pg_engine, expire_on_commit=False, autoflush=False) as session:
            session.execute(
                text("SELECT set_config('application_name', :name, true)"),
                {"name": name},
            )
            cached_activity = session.get(Activity, activity_id)
            cached_member = session.get(ActivityParticipation, (activity_id, users[1]))
            assert cached_activity is not None and cached_member is not None
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
        member = session.get(ActivityParticipation, (activity_id, users[1]))
        assert body.participant_count == int(
            member.status in ACTIVE_PARTICIPATION_STATUSES
        )
        assert body.checked_in_count == int(member.status == "CHECKED_IN")
        assert (member.checked_in_at is not None) is (member.status == "CHECKED_IN")
        if scenario == "duplicate":
            assert (
                outcomes.count((200, None))
                == outcomes.count((409, "Already checked in"))
                == 1
            )
        elif scenario == "leave":
            assert outcomes == (
                [(409, "Not participating in this activity"), (200, None)]
                if reverse
                else [(200, None), (409, "Checked-in participants cannot leave")]
            )
            assert member.status == ("LEFT" if reverse else "CHECKED_IN")
        elif scenario == "cancel":
            assert outcomes == (
                [(409, "Activity is cancelled"), (200, None)]
                if reverse
                else [(200, None), (200, None)]
            )
            assert body.status == "CANCELLED" and not any(
                body.permissions.model_dump().values()
            )
            assert member.status == ("CONFIRMED" if reverse else "CHECKED_IN")
        elif scenario == "location":
            assert outcomes == (
                [(409, "Outside check-in radius"), (200, None)]
                if reverse
                else [
                    (200, None),
                    (409, "Cannot change location after participants have checked in"),
                ]
            )
            assert body.latitude == (50 if reverse else AT_VENUE.latitude)
            assert member.status == ("CONFIRMED" if reverse else "CHECKED_IN")
        elif scenario == "time":
            assert outcomes == [
                (200, None),
                (409, "Cannot change schedule while participants are confirmed"),
            ]
            assert body.start_at == start and member.status == "CHECKED_IN"
        else:
            assert outcomes == (
                [(200, None), (200, None)]
                if reverse
                else [
                    (409, "Attendance must be confirmed before check-in"),
                    (200, None),
                ]
            )
            assert member.status == ("CHECKED_IN" if reverse else "CONFIRMED")


@pytest.mark.parametrize("zone", ["Asia/Kolkata", "Pacific/Honolulu"])
def test_check_in_utc_metadata_and_constant_service_queries(pg_engine, context, zone):
    activity_id, users, start = context
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
            body = activity_to_read(
                check_in_activity(session, activity_id, users[1], AT_VENUE)
            )
            assert (
                len(statements) == 4
            )  # Lock, member, ST_DWithin, response; HTTP adds auth.
        finally:
            event.remove(pg_engine, "before_cursor_execute", record)
        assert body.checkin_opens_at == start - timedelta(minutes=30)
        assert body.checkin_closes_at == start + timedelta(minutes=60)
        assert body.checkin_radius_m == 150
        assert body.current_user_participation.checked_in_at.utcoffset() == timedelta(0)


def test_mixed_check_in_states_counts_privacy_capacity_and_query_counts(
    pg_engine, context
):
    activity_id, users, _ = context
    with Session(pg_engine, expire_on_commit=False) as session:
        check_in_activity(session, activity_id, users[1], AT_VENUE)
        for user in users[2:]:
            join_activity(session, activity_id, user)
        confirm_activity(session, activity_id, users[3])
        leave_activity(session, activity_id, users[4])
        with pytest.raises(ActivityManagementError, match="below current"):
            update_activity(
                session, activity_id, users[0], ActivityUpdate(max_participants=2)
            )
        result = update_activity(
            session, activity_id, users[0], ActivityUpdate(max_participants=3)
        )
        assert result.participant_count == 3 and result.checked_in_count == 1
    statements = []

    def record(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    with pg_client(pg_engine) as client:
        headers = {"Authorization": f"Bearer {create_access_token(users[1])}"}
        event.listen(pg_engine, "before_cursor_execute", record)
        try:
            for url, params, auth, expected in [
                ("/api/v1/activities", {}, {}, 1),
                (f"/api/v1/activities/{activity_id}", {}, headers, 2),
                ("/api/v1/users/me/activities", {"relation": "joined"}, headers, 2),
            ]:
                statements.clear()
                response = client.get(url, params=params, headers=auth)
                assert response.status_code == 200 and len(statements) == expected
                body = (
                    response.json()[0]
                    if isinstance(response.json(), list)
                    else response.json()
                )
                assert (
                    body["participant_count"] == 3
                    and body["checked_in_count"] == 1
                    and body["available_slots"] == 0
                )
            body = client.get(
                f"/api/v1/activities/{activity_id}", headers=headers
            ).json()
            assert body["current_user_participation"]["checked_in_at"] is not None
            assert (
                client.get(f"/api/v1/activities/{activity_id}").json()[
                    "current_user_participation"
                ]
                is None
            )
        finally:
            event.remove(pg_engine, "before_cursor_execute", record)
