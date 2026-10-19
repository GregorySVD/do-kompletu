from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from geoalchemy2 import WKTElement
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from test_waitlist import NOW, START

from alembic import command
from app.core.config import get_settings
from app.models.activity import Activity
from app.models.user import User

pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


def read_rows(connection):
    return {
        row["user_id"]: dict(row)
        for row in connection.execute(
            text("SELECT * FROM activity_participations")
        ).mappings()
    }


def test_waitlist_migration_0008_0009_0008_0009_preserves_rows_and_constraints(
    monkeypatch,
):
    source = make_url(os.environ["POSTGRES_TEST_DATABASE_URL"])
    name = "dk_waitlist_migration_" + uuid4().hex
    target = source.set(database=name)
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    engine, created = None, False
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
        command.upgrade(config, "20261018_0008")
        with Session(engine) as session:
            users = [
                User(
                    email=f"migration{i}@example.com",
                    display_name=f"Migration{i}",
                    password_hash="unused",
                )
                for i in range(10)
            ]
            session.add_all(users)
            session.flush()
            activity = Activity(
                organizer_id=users[0].id,
                title="Waitlist migration",
                description="Retained data",
                category="gaming",
                start_at=START,
                end_at=START.replace(hour=18),
                location_name="Venue",
                address="Address",
                location=WKTElement("POINT(16.9 52.4)", srid=4326),
                min_participants=2,
                max_participants=8,
                price_type="FREE",
            )
            session.add(activity)
            session.flush()
            activity_id, user_ids = activity.id, [user.id for user in users]
            states = [
                "JOINED",
                "CONFIRMED",
                "CHECKED_IN",
                "COMPLETED",
                "NO_SHOW",
                "LEFT",
            ]
            for user, state in zip(user_ids[1:], states):
                session.execute(
                    text(
                        "INSERT INTO activity_participations (activity_id, user_id, status, joined_at, confirmed_at, "
                        "checked_in_at, completed_at, no_show_at, left_at) "
                        "VALUES (:activity, :user, :status, :now, :confirmed, :checked, :completed, :no_show, :left)"
                    ),
                    {
                        "activity": activity_id,
                        "user": user,
                        "status": state,
                        "now": NOW,
                        "confirmed": NOW
                        if state in {"CONFIRMED", "CHECKED_IN", "COMPLETED", "LEFT"}
                        else None,
                        "checked": NOW
                        if state in {"CHECKED_IN", "COMPLETED"}
                        else None,
                        "completed": NOW if state == "COMPLETED" else None,
                        "no_show": NOW if state == "NO_SHOW" else None,
                        "left": NOW if state == "LEFT" else None,
                    },
                )
            session.commit()
        with engine.connect() as connection:
            before = read_rows(connection)
        command.upgrade(config, "20261018_0009")
        with engine.begin() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0009"
            )
            columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("activity_participations")
            }
            assert columns["joined_at"]["nullable"]
            assert columns["joined_at"]["default"] is not None
            assert (
                columns["waitlisted_at"]["nullable"]
                and columns["waitlisted_at"]["type"].timezone
            )
            assert any(
                index["column_names"]
                == ["activity_id", "status", "waitlisted_at", "user_id"]
                for index in inspect(connection).get_indexes("activity_participations")
            )
            for user, row in read_rows(connection).items():
                assert row.pop("waitlisted_at") is None
                assert row == before[user]
            for user, state in zip(user_ids[7:], ["WAITLISTED", "LEFT", "JOINED"]):
                connection.execute(
                    text(
                        "INSERT INTO activity_participations (activity_id, user_id, status, joined_at, waitlisted_at, left_at) "
                        "VALUES (:activity, :user, :status, :joined, :now, :left)"
                    ),
                    {
                        "activity": activity_id,
                        "user": user,
                        "status": state,
                        "joined": NOW if state == "JOINED" else None,
                        "now": NOW,
                        "left": START if state == "LEFT" else None,
                    },
                )
            # Test the migrated PostgreSQL CHECKs, not only metadata-created SQLite.
            for changes in (
                "waitlisted_at = NULL",
                "joined_at = now()",
                "confirmed_at = now()",
                "checked_in_at = now()",
                "completed_at = now()",
                "no_show_at = now()",
                "left_at = now()",
                "status = 'JOINED'",
                "status = 'CONFIRMED', confirmed_at = now()",
                "status = 'NO_SHOW', no_show_at = now()",
                "status = 'INVALID'",
            ):
                with pytest.raises(IntegrityError) as caught, connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE activity_participations SET "
                            + changes
                            + " WHERE user_id = :user"
                        ),
                        {"user": user_ids[7]},
                    )
                assert caught.value.orig.sqlstate == "23514"
            for user in user_ids[1:7]:
                with pytest.raises(IntegrityError), connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE activity_participations SET joined_at = NULL WHERE user_id = :user"
                        ),
                        {"user": user},
                    )
            upgraded = read_rows(connection)
        command.downgrade(config, "20261018_0008")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0008"
            )
            down = read_rows(connection)
            assert len(down) == 9
            for user, original in before.items():
                assert (
                    down[user] == original
                )  # Active/final/previous LEFT all untouched.
            for user in user_ids[7:9]:
                assert down[user]["status"] == "LEFT"
                assert (
                    down[user]["joined_at"] == NOW
                )  # Documented legacy required timestamp.
                assert down[user]["left_at"] is not None
                assert down[user]["confirmed_at"] is None
                assert down[user]["checked_in_at"] is None
            assert (
                down[user_ids[8]]["left_at"] == START
            )  # Real queue departure preserved.
            assert down[user_ids[9]] == {
                key: value
                for key, value in upgraded[user_ids[9]].items()
                if key != "waitlisted_at"
            }
            assert not next(
                column
                for column in inspect(connection).get_columns("activity_participations")
                if column["name"] == "joined_at"
            )["nullable"]
        command.upgrade(config, "20261018_0009")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0009"
            )
            for user, row in read_rows(connection).items():
                assert row.pop("waitlisted_at") is None
                assert (
                    row == down[user]
                )  # No reconstruction of a queue lost on downgrade.
            assert connection.scalar(text("SELECT count(*) FROM users")) == 10
            assert connection.scalar(text("SELECT count(*) FROM activities")) == 1
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
