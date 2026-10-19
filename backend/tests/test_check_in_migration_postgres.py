from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from geoalchemy2 import WKTElement
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.models.activity import Activity
from app.models.user import User

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    POSTGRES_TEST_DATABASE_URL is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


def test_check_in_migration_preserves_rows_and_converts_checked_in_on_downgrade(
    monkeypatch,
):
    source = make_url(POSTGRES_TEST_DATABASE_URL)
    name = "dk_checkin_migration_" + uuid4().hex
    target = source.set(database=name)
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    engine = None
    created = False
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        engine = create_engine(target)
        with engine.begin() as connection:
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        monkeypatch.setenv("DATABASE_URL", target.render_as_string(hide_password=False))
        get_settings.cache_clear()
        backend = Path(__file__).resolve().parents[1]
        config = Config(str(backend / "alembic.ini"))
        config.set_main_option("script_location", str(backend / "alembic"))
        command.upgrade(config, "20261018_0006")
        now = datetime.now(UTC)
        with Session(engine) as session:
            users = [
                User(
                    email=f"checkin-migration-{i}@example.com",
                    display_name=f"CheckInMigration{i}",
                    password_hash="unused",
                )
                for i in range(4)
            ]
            session.add_all(users)
            session.flush()
            activity = Activity(
                organizer_id=users[0].id,
                title="Migration check-in",
                description="Existing data survives the migration.",
                category="gaming",
                start_at=now + timedelta(minutes=15),
                end_at=now + timedelta(hours=2),
                location_name="Venue",
                address="Address",
                location=WKTElement("POINT(16.9 52.4)", srid=4326),
                min_participants=2,
                max_participants=3,
                price_type="FREE",
            )
            session.add(activity)
            session.flush()
            activity_id, user_ids = activity.id, [user.id for user in users]
            for user, state, confirmed, left in [
                (user_ids[1], "JOINED", None, None),
                (user_ids[2], "CONFIRMED", now, None),
                (user_ids[3], "LEFT", now, now),
            ]:
                session.execute(
                    text(
                        "INSERT INTO activity_participations (activity_id, user_id, status, joined_at, confirmed_at, left_at) VALUES (:activity, :user, :status, :joined, :confirmed, :left)"
                    ),
                    {
                        "activity": activity_id,
                        "user": user,
                        "status": state,
                        "joined": now,
                        "confirmed": confirmed,
                        "left": left,
                    },
                )
            session.commit()
        with engine.connect() as connection:
            before = {
                row["user_id"]: dict(row)
                for row in connection.execute(
                    text("SELECT * FROM activity_participations")
                ).mappings()
            }
        command.upgrade(config, "20261018_0007")
        with engine.begin() as connection:
            columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("activity_participations")
            }
            assert set(columns) == {
                "activity_id",
                "user_id",
                "status",
                "joined_at",
                "left_at",
                "confirmed_at",
                "checked_in_at",
            }
            assert (
                columns["checked_in_at"]["nullable"]
                and columns["checked_in_at"]["type"].timezone
            )
            rows = (
                connection.execute(text("SELECT * FROM activity_participations"))
                .mappings()
                .all()
            )
            for row in rows:
                assert row["checked_in_at"] is None
                assert {
                    key: value for key, value in row.items() if key != "checked_in_at"
                } == before[row["user_id"]]
            assert inspect(connection).get_pk_constraint("activity_participations")[
                "constrained_columns"
            ] == ["activity_id", "user_id"]
            for values in [
                "status = 'INVALID'",
                "status = 'CHECKED_IN'",
                "checked_in_at = now()",
            ]:
                with pytest.raises(IntegrityError) as caught, connection.begin_nested():
                    connection.execute(
                        text("UPDATE activity_participations SET " + values)
                    )
                assert caught.value.orig.sqlstate == "23514"
            connection.execute(
                text(
                    "UPDATE activity_participations SET status = 'CHECKED_IN', checked_in_at = :now WHERE user_id = :user"
                ),
                {"now": now, "user": user_ids[2]},
            )

        command.downgrade(config, "20261018_0006")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0006"
            )
            assert "checked_in_at" not in {
                column["name"]
                for column in inspect(connection).get_columns("activity_participations")
            }
            rows = {
                row["user_id"]: dict(row)
                for row in connection.execute(
                    text("SELECT * FROM activity_participations")
                ).mappings()
            }
            assert (
                rows == before
            )  # Checked-in becomes CONFIRMED; no rows/timestamps are deleted.
            assert connection.scalar(text("SELECT count(*) FROM users")) == 4
            assert connection.scalar(text("SELECT count(*) FROM activities")) == 1
        command.upgrade(config, "20261018_0007")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0007"
            )
            rows = (
                connection.execute(text("SELECT * FROM activity_participations"))
                .mappings()
                .all()
            )
            assert len(rows) == 3
            assert all(row["checked_in_at"] is None for row in rows)
            assert {row["user_id"]: row["status"] for row in rows} == {
                user: row["status"] for user, row in before.items()
            }
    finally:
        get_settings.cache_clear()
        if engine is not None:
            engine.dispose()
        try:
            if created:
                with admin.connect() as connection:
                    connection.execute(text(f'DROP DATABASE "{name}"'))
        finally:
            admin.dispose()
