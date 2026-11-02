from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from my_activities_data import AS_OF, freeze_activity_clock, seed_my_activities
from sqlalchemy import create_engine, event, text, update
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.db.session import get_db
from app.main import app
from app.models.activity import Activity

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    POSTGRES_TEST_DATABASE_URL is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)
ENDPOINT = "/api/v1/users/me/activities"


@pytest.fixture
def pg_context(monkeypatch):
    freeze_activity_clock(monkeypatch)
    engine = create_engine(
        POSTGRES_TEST_DATABASE_URL, connect_args={"connect_timeout": 5}
    )
    assert engine.dialect.name == "postgresql"
    previous_overrides = app.dependency_overrides.copy()
    try:
        with engine.connect() as connection:
            outer = connection.begin()
            session = Session(
                bind=connection,
                join_transaction_mode="create_savepoint",
                expire_on_commit=False,
            )
            try:
                data = seed_my_activities(session)

                def database():
                    with Session(
                        bind=connection,
                        join_transaction_mode="create_savepoint",
                        autoflush=False,
                        expire_on_commit=False,
                    ) as request_session:
                        yield request_session

                app.dependency_overrides[get_db] = database
                with TestClient(app) as client:
                    yield client, data, connection
            finally:
                session.close()
                outer.rollback()
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        engine.dispose()


def page(context, relation, **params):
    client, data, _ = context
    response = client.get(
        ENDPOINT,
        params={"relation": relation, **params},
        headers={"Authorization": f"Bearer {create_access_token(data.users[0].id)}"},
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize("relation", ["organized", "joined"])
def test_postgres_scoped_membership_counts_state_and_postgis_coordinates(
    pg_context, relation
):
    client, data, _ = pg_context
    items = page(pg_context, relation)
    if relation == "organized":
        assert [item["id"] for item in items] == data.ids(
            "own_ongoing", "own_upcoming", "own_recent", "own_old"
        )
        assert all(item["organizer"]["id"] == str(data.users[0].id) for item in items)
        assert all(item["current_user_participation"] is None for item in items)
        for item in items:
            assert item["permissions"]["can_edit"] is (item["status"] == "PUBLISHED")
            assert item["permissions"]["can_cancel"] is (item["status"] != "ENDED")
            assert item["permissions"]["can_view_gallery"] is (
                AS_OF < datetime.fromisoformat(item["end_at"]) + timedelta(hours=72)
            )
            assert not any(
                value
                for key, value in item["permissions"].items()
                if key not in {"can_edit", "can_cancel", "can_view_gallery"}
            )
        assert items[0]["participant_count"] == 1
        assert items[0]["available_slots"] == 3
    else:
        assert all(item["organizer"]["id"] != str(data.users[0].id) for item in items)
        assert all(
            item["current_user_participation"]["status"] == "JOINED" for item in items
        )
        assert set(data.ids("not_joined", "unrelated", "own_ongoing")).isdisjoint(
            item["id"] for item in items
        )
        by_id = {item["id"]: item for item in items}
        full = by_id[data.ids("joined_ongoing")[0]]
        assert full["participant_count"] == 2
        assert full["available_slots"] == 0
        assert full["permissions"]["can_leave"] is False
        unlimited = by_id[data.ids("joined_unlimited")[0]]
        assert unlimited["participant_count"] == 1
        assert unlimited["max_participants"] is unlimited["available_slots"] is None
        ended = by_id[data.ids("history_new_a")[0]]
        assert ended["permissions"]["can_leave"] is False
        own_state = client.get(
            f"/api/v1/activities/{full['id']}",
            headers={
                "Authorization": f"Bearer {create_access_token(data.users[0].id)}",
            },
        ).json()
        assert own_state == full
        public_state = client.get(f"/api/v1/activities/{full['id']}").json()
        assert public_state["current_user_participation"] is None
    for item in items:
        assert item["latitude"] == pytest.approx(52.4005)
        assert item["longitude"] == pytest.approx(16.9516)
        assert item["checked_in_count"] == item["waitlist_count"] == 0


@pytest.mark.parametrize("database_zone", ["Asia/Kolkata", "Pacific/Honolulu"])
def test_postgres_timestamptz_boundaries_ignore_input_and_connection_timezones(
    pg_context, database_zone
):
    _, data, connection = pg_context
    connection.execute(
        text("SELECT set_config('TimeZone', :zone, true)"), {"zone": database_zone}
    )
    positive_offset = timezone(timedelta(hours=5, minutes=30))
    negative_offset = timezone(timedelta(hours=-7))
    for name, delta, offset in [
        ("boundary", timedelta(0), positive_offset),
        ("just_before", -timedelta(microseconds=1), negative_offset),
        ("just_after", timedelta(microseconds=1), positive_offset),
    ]:
        connection.execute(
            update(Activity)
            .where(Activity.id == data.activities[name].id)
            .values(
                end_at=(AS_OF + delta).astimezone(offset),
            )
        )
    upcoming = page(pg_context, "joined", scope="upcoming")
    history = page(pg_context, "joined", scope="history")
    upcoming_ids = {item["id"] for item in upcoming}
    history_ids = {item["id"] for item in history}
    assert upcoming_ids.isdisjoint(history_ids)
    assert data.ids("just_after")[0] in upcoming_ids
    assert set(data.ids("boundary", "just_before")) <= history_ids
    boundary = next(item for item in history if item["id"] == data.ids("boundary")[0])
    assert boundary["end_at"] == "2030-06-01T10:00:00Z"
    assert boundary["status"] == "ENDED"
    assert boundary["permissions"]["can_leave"] is False


@pytest.mark.parametrize("scope", [None, "upcoming", "history"])
def test_postgres_sorting_uuid_ties_and_pagination(pg_context, scope):
    params = {"scope": scope} if scope is not None else {}
    items = page(pg_context, "joined", **params)
    upcoming = [
        "joined_ongoing",
        "just_after",
        "start_boundary",
        "joined_a",
        "joined_b",
        "joined_unlimited",
    ]
    history = [
        "boundary",
        "just_before",
        "history_new_a",
        "history_new_b",
        "history_old",
    ]
    names = (
        upcoming
        if scope == "upcoming"
        else history
        if scope == "history"
        else upcoming + history
    )
    assert [item["id"] for item in items] == pg_context[1].ids(*names)
    assert page(pg_context, "joined", **params, limit=2, offset=1) == items[1:3]
    assert page(pg_context, "joined", **params, offset=100) == []


@pytest.mark.parametrize("relation", ["organized", "joined"])
def test_postgres_query_count_is_constant_for_my_and_public_activity_pages(
    pg_context, relation
):
    client, _, connection = pg_context
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(connection, "before_cursor_execute", record)
    try:
        page(pg_context, relation, limit=1)
        assert len(statements) == 2
        statements.clear()
        items = page(pg_context, relation, limit=100)
        assert len(items) > 1
        assert len(statements) == 2  # Authentication + one complete SQL projection.
        statement = statements[-1]
        assert "ST_Y" in statement and "ST_X" in statement
        assert "count(" in statement
        assert "JOIN users" in statement
        statements.clear()
        assert (
            client.get("/api/v1/activities", params={"limit": 100}).status_code == 200
        )
        assert len(statements) == 1
    finally:
        event.remove(connection, "before_cursor_execute", record)
