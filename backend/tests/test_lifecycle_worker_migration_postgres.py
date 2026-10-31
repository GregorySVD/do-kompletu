from __future__ import annotations

import os
from datetime import timedelta
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
from test_lifecycle_worker import DEADLINE, EARLY, OPEN, START

from alembic import command
from app.core.config import get_settings
from app.models.activity import Activity
from app.models.user import User

pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)
NEW_COLUMNS = {"confirmation_expired_at", "waitlist_expired_at"}


def rows(connection):
    return {
        row["user_id"]: dict(row)
        for row in connection.execute(
            text("SELECT * FROM activity_participations")
        ).mappings()
    }


def test_0010_upgrade_downgrade_upgrade_preserves_rows_and_expiry_origin(monkeypatch):
    source = make_url(os.environ["POSTGRES_TEST_DATABASE_URL"])
    name = "dk_lifecycle_migration_" + uuid4().hex
    target = source.set(database=name)
    admin = create_engine(source.set(database="postgres"), isolation_level="AUTOCOMMIT")
    engine, created = None, False
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
            created = True
        engine = create_engine(target)
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        monkeypatch.setenv("DATABASE_URL", target.render_as_string(hide_password=False))
        get_settings.cache_clear()
        root = Path(__file__).resolve().parents[1]
        config = Config(str(root / "alembic.ini"))
        config.set_main_option("script_location", str(root / "alembic"))
        command.upgrade(config, "20261018_0009")
        with Session(engine) as session:
            users = [
                User(
                    email=f"migrate-expiry{i}@example.com",
                    display_name=f"MigrateExpiry{i}",
                    password_hash="unused",
                )
                for i in range(9)
            ]
            insert_legacy_users(session, users)
            session.flush()
            activity = Activity(
                organizer_id=users[0].id,
                title="Expiry migration",
                description="Preserve all evidence",
                category="gaming",
                start_at=START,
                end_at=START + timedelta(hours=2),
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
            for user, state in zip(
                user_ids[1:],
                [
                    "JOINED",
                    "CONFIRMED",
                    "CHECKED_IN",
                    "COMPLETED",
                    "NO_SHOW",
                    "LEFT",
                    "WAITLISTED",
                    "LEFT",
                ],
            ):
                session.execute(
                    text(
                        "INSERT INTO activity_participations (activity_id,user_id,status,joined_at,waitlisted_at,confirmed_at,checked_in_at,completed_at,no_show_at,left_at) "
                        "VALUES (:activity,:user,:status,:joined,:waited,:confirmed,:checked,:completed,:no_show,:left)"
                    ),
                    {
                        "activity": activity_id,
                        "user": user,
                        "status": state,
                        "joined": None
                        if state == "WAITLISTED" or user == user_ids[8]
                        else EARLY,
                        "waited": EARLY
                        if state in {"JOINED", "WAITLISTED"} or user == user_ids[8]
                        else None,
                        "confirmed": OPEN
                        if state in {"CONFIRMED", "CHECKED_IN", "COMPLETED", "LEFT"}
                        and user != user_ids[8]
                        else None,
                        "checked": START
                        if state in {"CHECKED_IN", "COMPLETED"}
                        else None,
                        "completed": START + timedelta(hours=2)
                        if state == "COMPLETED"
                        else None,
                        "no_show": START + timedelta(hours=2)
                        if state == "NO_SHOW"
                        else None,
                        "left": OPEN if state == "LEFT" else None,
                    },
                )
            session.commit()
        with engine.connect() as conn:
            before = rows(conn)
        command.upgrade(config, "20261019_0010")
        with engine.begin() as conn:
            columns = {
                column["name"]: column
                for column in inspect(conn).get_columns("activity_participations")
            }
            assert columns["status"]["type"].length == 24
            assert all(
                columns[name]["nullable"] and columns[name]["type"].timezone
                for name in NEW_COLUMNS
            )
            for user, row in rows(conn).items():
                assert all(row.pop(name) is None for name in NEW_COLUMNS)
                assert row == before[user]
            for changes, user in [
                ("status='CONFIRMATION_EXPIRED'", user_ids[1]),
                (
                    "status='CONFIRMATION_EXPIRED',confirmation_expired_at=now()",
                    user_ids[2],
                ),
                ("status='WAITLIST_EXPIRED'", user_ids[7]),
                ("status='WAITLIST_EXPIRED',waitlist_expired_at=now()", user_ids[1]),
                ("confirmation_expired_at=now()", user_ids[1]),
                ("waitlist_expired_at=now()", user_ids[7]),
            ]:
                with pytest.raises(IntegrityError) as caught, conn.begin_nested():
                    conn.execute(
                        text(
                            "UPDATE activity_participations SET "
                            + changes
                            + " WHERE user_id=:user"
                        ),
                        {"user": user},
                    )
                assert caught.value.orig.sqlstate == "23514"
            conn.execute(
                text(
                    "UPDATE activity_participations SET status='CONFIRMATION_EXPIRED',confirmation_expired_at=:time WHERE user_id=:user"
                ),
                {"time": DEADLINE, "user": user_ids[1]},
            )
            conn.execute(
                text(
                    "UPDATE activity_participations SET status='WAITLIST_EXPIRED',waitlist_expired_at=:time WHERE user_id=:user"
                ),
                {"time": START, "user": user_ids[7]},
            )
            upgraded = rows(conn)
            assert upgraded[user_ids[1]]["waitlisted_at"] == EARLY
            assert upgraded[user_ids[7]]["joined_at"] is None
        command.downgrade(config, "20261018_0009")
        with engine.connect() as conn:
            assert (
                conn.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0009"
            )
            down = rows(conn)
            assert len(down) == 8
            for user in user_ids[2:7] + user_ids[8:]:
                assert down[user] == before[user]
            assert down[user_ids[1]] == {
                **before[user_ids[1]],
                "status": "LEFT",
                "left_at": DEADLINE,
            }
            assert down[user_ids[7]] == before[user_ids[7]]
            columns = {
                column["name"]: column
                for column in inspect(conn).get_columns("activity_participations")
            }
            assert (
                not NEW_COLUMNS & columns.keys()
                and columns["status"]["type"].length == 16
            )
        command.upgrade(config, "20261019_0010")
        with engine.connect() as conn:
            assert (
                conn.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261019_0010"
            )
            for user, row in rows(conn).items():
                assert all(row.pop(name) is None for name in NEW_COLUMNS)
                assert row == down[user]
            assert conn.scalar(text("SELECT count(*) FROM users")) == 9
            assert conn.scalar(text("SELECT count(*) FROM activities")) == 1
    finally:
        get_settings.cache_clear()
        if engine is not None:
            engine.dispose()
        try:
            if created:
                with admin.connect() as conn:
                    conn.execute(text(f'DROP DATABASE "{name}"'))
        finally:
            admin.dispose()
