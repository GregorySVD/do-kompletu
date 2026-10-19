import os
from datetime import timedelta, timezone
from uuid import uuid4

import pytest
import test_my_activities_postgres as postgres_data
from fastapi.testclient import TestClient
from my_activities_data import AS_OF
from sqlalchemy import event, text, update

from app.core.config import get_settings
from app.db.session import get_session_factory, reset_db_state
from app.main import app
from app.models.activity import Activity

pg_context = postgres_data.pg_context

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    POSTGRES_TEST_DATABASE_URL is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


@pytest.mark.parametrize("database_zone", ["Asia/Kolkata", "Pacific/Honolulu"])
def test_postgres_discovery_filters_before_pagination_at_utc_boundary(
    pg_context, database_zone
):
    client, data, connection = pg_context
    marker = uuid4().hex
    for activity in data.activities.values():
        connection.execute(
            update(Activity).where(Activity.id == activity.id).values(
                title=f"{marker} {activity.title}"
            )
        )
    connection.execute(
        text("SELECT set_config('TimeZone', :zone, true)"), {"zone": database_zone}
    )
    offset = timezone(timedelta(hours=5, minutes=30))
    for name, delta in [
        ("boundary", timedelta(0)),
        ("just_before", -timedelta(microseconds=1)),
        ("just_after", timedelta(microseconds=1)),
    ]:
        connection.execute(
            update(Activity).where(Activity.id == data.activities[name].id).values(
                end_at=(AS_OF + delta).astimezone(offset)
            )
        )
    connection.execute(
        update(Activity).where(Activity.id == data.activities["joined_a"].id).values(
            cancelled_at=AS_OF
        )
    )
    response = client.get("/api/v1/activities", params={"query": marker, "limit": 3})
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == data.ids(
        "own_ongoing", "joined_ongoing", "just_after"
    )
    assert all(item["status"] == "ONGOING" for item in response.json())
    page = client.get(
        "/api/v1/activities",
        params={"query": f"{marker} Joined", "price_type": "FREE", "limit": 1, "offset": 1},
    )
    assert page.status_code == 200
    assert [item["id"] for item in page.json()] == data.ids("joined_b")


def test_postgres_readiness_uses_normal_configured_session(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_TEST_DATABASE_URL)
    get_settings.cache_clear()
    reset_db_state()
    engine = get_session_factory().kw["bind"]
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        assert engine.dialect.name == "postgresql"
        with TestClient(app) as client:
            response = client.get("/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert statements == ["SELECT 1"]
    finally:
        event.remove(engine, "before_cursor_execute", record)
        engine.dispose()
        reset_db_state()
        get_settings.cache_clear()
