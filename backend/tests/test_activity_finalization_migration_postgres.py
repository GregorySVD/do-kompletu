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
FINAL_COLUMNS = {"completed_at", "no_show_at"}


def read_rows(connection):
    return {
        row["user_id"]: dict(row)
        for row in connection.execute(
            text("SELECT * FROM activity_participations")
        ).mappings()
    }


def test_finalization_migration_cycle_preserves_evidence_and_restores_prior_states(
    monkeypatch,
):
    source = make_url(POSTGRES_TEST_DATABASE_URL)
    name = "dk_finalization_migration_" + uuid4().hex
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
        command.upgrade(config, "20261018_0007")
        now = datetime(2030, 8, 8, 18, tzinfo=UTC)
        with Session(engine) as session:
            users = [
                User(
                    email=f"final-migration-{i}@example.com",
                    display_name=f"FinalMigration{i}",
                    password_hash="unused",
                )
                for i in range(5)
            ]
            insert_legacy_users(session, users)
            session.flush()
            activity = Activity(
                organizer_id=users[0].id,
                title="Final attendance migration",
                description="Existing attendance evidence survives.",
                category="gaming",
                start_at=now - timedelta(hours=2),
                end_at=now,
                location_name="Venue",
                address="Address",
                location=WKTElement("POINT(16.9 52.4)", srid=4326),
                min_participants=2,
                max_participants=4,
                price_type="FREE",
            )
            session.add(activity)
            session.flush()
            activity_id, user_ids = activity.id, [user.id for user in users]
            for user, state, confirmed, checked, left in [
                (user_ids[1], "JOINED", None, None, None),
                (user_ids[2], "CONFIRMED", now - timedelta(hours=3), None, None),
                (
                    user_ids[3],
                    "CHECKED_IN",
                    now - timedelta(hours=3),
                    now - timedelta(hours=2),
                    None,
                ),
                (
                    user_ids[4],
                    "LEFT",
                    now - timedelta(hours=3),
                    None,
                    now - timedelta(hours=2),
                ),
            ]:
                session.execute(
                    text(
                        "INSERT INTO activity_participations (activity_id, user_id, status, joined_at, confirmed_at, checked_in_at, left_at) "
                        "VALUES (:activity, :user, :status, :joined, :confirmed, :checked, :left)"
                    ),
                    {
                        "activity": activity_id,
                        "user": user,
                        "status": state,
                        "joined": now - timedelta(days=1),
                        "confirmed": confirmed,
                        "checked": checked,
                        "left": left,
                    },
                )
            session.commit()
        with engine.connect() as connection:
            before = read_rows(connection)

        command.upgrade(config, "20261018_0008")
        with engine.begin() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0008"
            )
            columns = {
                column["name"]: column
                for column in inspect(connection).get_columns("activity_participations")
            }
            assert set(columns) == set(next(iter(before.values()))) | FINAL_COLUMNS
            assert all(
                columns[key]["nullable"] and columns[key]["type"].timezone
                for key in FINAL_COLUMNS
            )
            for user, row in read_rows(connection).items():
                assert all(row[key] is None for key in FINAL_COLUMNS)
                assert {
                    key: value for key, value in row.items() if key not in FINAL_COLUMNS
                } == before[user]
            inspector = inspect(connection)
            assert inspector.get_pk_constraint("activity_participations")[
                "constrained_columns"
            ] == ["activity_id", "user_id"]
            assert {
                tuple(fk["constrained_columns"])
                for fk in inspector.get_foreign_keys("activity_participations")
            } == {("activity_id",), ("user_id",)}
            # PostgreSQL itself enforces each invalid final-state combination.
            for values, user in [
                ("status = 'COMPLETED'", user_ids[3]),
                ("status = 'NO_SHOW'", user_ids[1]),
                ("status = 'COMPLETED', completed_at = now()", user_ids[2]),
                ("status = 'NO_SHOW', no_show_at = now()", user_ids[3]),
                ("completed_at = now()", user_ids[1]),
                ("no_show_at = now()", user_ids[4]),
                ("status = 'UNKNOWN'", user_ids[1]),
            ]:
                with pytest.raises(IntegrityError) as caught, connection.begin_nested():
                    connection.execute(
                        text(
                            "UPDATE activity_participations SET "
                            + values
                            + " WHERE user_id = :user"
                        ),
                        {"user": user},
                    )
                assert caught.value.orig.sqlstate == "23514"
            connection.execute(
                text(
                    "UPDATE activity_participations SET status = 'NO_SHOW', no_show_at = :now WHERE user_id IN (:joined, :confirmed)"
                ),
                {"now": now, "joined": user_ids[1], "confirmed": user_ids[2]},
            )
            connection.execute(
                text(
                    "UPDATE activity_participations SET status = 'COMPLETED', completed_at = :now WHERE user_id = :user"
                ),
                {"now": now, "user": user_ids[3]},
            )
            final = read_rows(connection)
            for user in user_ids[1:4]:
                assert {
                    key: value
                    for key, value in final[user].items()
                    if key not in FINAL_COLUMNS | {"status"}
                } == {
                    key: value for key, value in before[user].items() if key != "status"
                }
            assert final[user_ids[1]]["confirmed_at"] is None
            assert (
                final[user_ids[3]]["checked_in_at"]
                == before[user_ids[3]]["checked_in_at"]
            )

        command.downgrade(config, "20261018_0007")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0007"
            )
            assert not FINAL_COLUMNS & {
                column["name"]
                for column in inspect(connection).get_columns("activity_participations")
            }
            # In particular, NO_SHOW from JOINED returns to JOINED without
            # inventing a confirmed_at timestamp to satisfy the old constraint.
            assert read_rows(connection) == before
            assert connection.scalar(text("SELECT count(*) FROM users")) == 5
            assert connection.scalar(text("SELECT count(*) FROM activities")) == 1
        command.upgrade(config, "20261018_0008")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261018_0008"
            )
            for user, row in read_rows(connection).items():
                assert all(row[key] is None for key in FINAL_COLUMNS)
                assert {
                    key: value for key, value in row.items() if key not in FINAL_COLUMNS
                } == before[user]
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
