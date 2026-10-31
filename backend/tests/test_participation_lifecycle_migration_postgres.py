from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from geoalchemy2 import WKTElement
from migration_data import insert_legacy_users
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


def test_postgres_migration_backfill_constraints_and_upgrade_downgrade_upgrade(
    monkeypatch,
):
    """Only a generated temporary database is downgraded or dropped."""
    source = make_url(POSTGRES_TEST_DATABASE_URL)
    name = "dk_lifecycle_migration_" + uuid4().hex
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
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        config.set_main_option(
            "script_location", str(Path(__file__).resolve().parents[1] / "alembic")
        )
        command.upgrade(config, "20261018_0005")
        now = datetime.now(UTC)
        with Session(engine) as session:
            users = [
                User(
                    email=f"migration-{i}@example.com",
                    display_name=f"Migration{i}",
                    password_hash="unused",
                )
                for i in range(4)
            ]
            insert_legacy_users(session, users)
            session.flush()
            activity = Activity(
                organizer_id=users[0].id,
                title="Migration fixture",
                description="Existing activity is preserved.",
                category="gaming",
                start_at=now + timedelta(days=2),
                end_at=now + timedelta(days=2, hours=1),
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
            for user in user_ids[1:]:
                session.execute(
                    text(
                        "INSERT INTO activity_participations (activity_id, user_id, joined_at) VALUES (:activity, :user, :joined)"
                    ),
                    {"activity": activity_id, "user": user, "joined": now},
                )
            session.commit()

        command.upgrade(config, "20261018_0006")
        with engine.connect() as connection:
            rows = (
                connection.execute(text("SELECT * FROM activity_participations"))
                .mappings()
                .all()
            )
            assert len(rows) == 3
            assert all(
                row["status"] == "JOINED"
                and row["joined_at"] == now
                and row["left_at"] is None
                and row["confirmed_at"] is None
                for row in rows
            )
            columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("activity_participations")
            }
            assert columns["status"]["nullable"] is False
            assert "JOINED" in columns["status"]["default"]
            assert (
                columns["left_at"]["nullable"] and columns["confirmed_at"]["nullable"]
            )
            assert inspect(connection).get_pk_constraint("activity_participations")[
                "constrained_columns"
            ] == ["activity_id", "user_id"]
        with engine.begin() as connection:
            for sql, constraint in [
                (
                    "UPDATE activity_participations SET status = 'INVALID'",
                    "ck_activity_participations_status",
                ),
                (
                    "UPDATE activity_participations SET status = 'CONFIRMED'",
                    "ck_activity_participations_state_timestamps",
                ),
                (
                    "UPDATE activity_participations SET status = 'LEFT'",
                    "ck_activity_participations_state_timestamps",
                ),
            ]:
                with pytest.raises(IntegrityError) as caught, connection.begin_nested():
                    connection.execute(text(sql))
                assert caught.value.orig.sqlstate == "23514"
                # Invalid statuses can violate both CHECKs; PostgreSQL chooses
                # which one to report. Timestamp-only violations are specific.
                assert caught.value.orig.diag.constraint_name in {
                    constraint,
                    "ck_activity_participations_state_timestamps",
                }
            with pytest.raises(IntegrityError) as caught, connection.begin_nested():
                connection.execute(
                    text(
                        "INSERT INTO activity_participations (activity_id, user_id) VALUES (:activity, :user)"
                    ),
                    {"activity": activity_id, "user": user_ids[1]},
                )
            assert caught.value.orig.sqlstate == "23505"
            connection.execute(
                text(
                    "UPDATE activity_participations SET status = 'CONFIRMED', confirmed_at = :now WHERE user_id = :user"
                ),
                {"now": now, "user": user_ids[2]},
            )
            connection.execute(
                text(
                    "UPDATE activity_participations SET status = 'LEFT', left_at = :now WHERE user_id = :user"
                ),
                {"now": now, "user": user_ids[3]},
            )

        command.downgrade(config, "20261018_0005")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0005"
            )
            assert "status" not in {
                column["name"]
                for column in inspect(connection).get_columns("activity_participations")
            }
            assert set(
                connection.scalars(text("SELECT user_id FROM activity_participations"))
            ) == set(user_ids[1:3])
            assert connection.scalar(text("SELECT count(*) FROM users")) == 4
            assert connection.scalar(text("SELECT count(*) FROM activities")) == 1
        command.upgrade(config, "20261018_0006")
        with engine.connect() as connection:
            rows = (
                connection.execute(text("SELECT * FROM activity_participations"))
                .mappings()
                .all()
            )
            assert len(rows) == 2
            assert all(
                row["status"] == "JOINED"
                and row["confirmed_at"] is None
                and row["left_at"] is None
                for row in rows
            )
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0006"
            )
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
