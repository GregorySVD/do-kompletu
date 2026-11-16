"""Organizer backfill is verified only against isolated real PostgreSQL databases."""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation, ParticipationStatus
from app.models.user import User
from app.services.activity_service import _location_value

pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)

CUTOFF = datetime(2026, 11, 8, tzinfo=UTC)
PREVIOUS_REVISION = "20261031_0012"
REVISION = "20261108_0013"


@pytest.fixture
def migration_database(monkeypatch):
    """Only a generated task database is migrated, downgraded, or dropped."""
    source = make_url(os.environ["POSTGRES_TEST_DATABASE_URL"])
    name = "dk_organizer_migration_" + uuid4().hex
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
        command.upgrade(config, PREVIOUS_REVISION)
        yield engine, config
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


def seed_legacy_activity(session, *, end_at=None, cancelled=False, status=None):
    suffix = uuid4().hex
    organizer = User(
        email=f"organizer-migration-{suffix}@example.com",
        display_name=f"OrganizerMigration{suffix}",
        password_hash="unused",
        points_total=17,
        created_at=CUTOFF - timedelta(days=30),
    )
    session.add(organizer)
    session.flush()
    end_at = end_at or CUTOFF + timedelta(days=2)
    activity = Activity(
        organizer_id=organizer.id,
        title="Legacy organizer fixture",
        description="Existing legacy activity is preserved.",
        category="gaming",
        start_at=end_at - timedelta(hours=2),
        end_at=end_at,
        cancelled_at=CUTOFF - timedelta(days=1) if cancelled else None,
        location_name="Venue",
        address="Address",
        location=_location_value(session, 52.4, 16.9),
        min_participants=2,
        max_participants=2,
        price_type="FREE",
        created_at=CUTOFF - timedelta(days=2),
        updated_at=CUTOFF - timedelta(days=2),
    )
    session.add(activity)
    session.flush()
    if status is not None:
        queued = status in {"WAITLISTED", "WAITLIST_EXPIRED"}
        row = ActivityParticipation(
            activity_id=activity.id,
            user_id=organizer.id,
            status=status,
            joined_at=None if queued else CUTOFF - timedelta(days=1),
            waitlisted_at=CUTOFF - timedelta(days=1) if queued else None,
            confirmed_at=CUTOFF - timedelta(hours=20)
            if status in {"CONFIRMED", "CHECKED_IN", "COMPLETED"}
            else None,
            checked_in_at=CUTOFF - timedelta(hours=1)
            if status in {"CHECKED_IN", "COMPLETED"}
            else None,
            completed_at=CUTOFF if status == "COMPLETED" else None,
            no_show_at=CUTOFF if status == "NO_SHOW" else None,
            left_at=CUTOFF if status == "LEFT" else None,
            confirmation_expired_at=CUTOFF
            if status == "CONFIRMATION_EXPIRED"
            else None,
            waitlist_expired_at=CUTOFF if status == "WAITLIST_EXPIRED" else None,
        )
        session.add(row)
    session.commit()
    return activity.id, organizer.id


def snapshot(connection):
    return {
        table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1, 2")).all()
        for table in (
            "users",
            "activities",
            "activity_participations",
            "activity_photos",
        )
    }


def test_active_legacy_backfill_uses_fixed_cutoff_and_actual_confirmation_time(
    migration_database,
):
    engine, config = migration_database
    with Session(engine, expire_on_commit=False) as session:
        pairs = [
            seed_legacy_activity(session, end_at=end)
            for end in (
                CUTOFF + timedelta(days=2),  # Upcoming at the fixed cutoff.
                CUTOFF + timedelta(hours=1),  # Already ongoing at the cutoff.
                CUTOFF + timedelta(microseconds=1),
            )
        ]
    with engine.connect() as connection:
        before = snapshot(connection)
        applied_after = connection.scalar(text("SELECT clock_timestamp()"))
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        applied_before = connection.scalar(text("SELECT clock_timestamp()"))
        after = snapshot(connection)
        for table in before.keys() - {"activity_participations"}:
            assert before[table] == after[table]
        rows = (
            connection.execute(text("SELECT * FROM activity_participations"))
            .mappings()
            .all()
        )
        assert {(r["activity_id"], r["user_id"]) for r in rows} == set(pairs)
        assert len({r["confirmed_at"] for r in rows}) == 1
        for row in rows:
            assert row["status"] == "CONFIRMED"
            assert row["joined_at"] == row["confirmed_at"]
            assert applied_after <= row["confirmed_at"] <= applied_before
            assert all(
                row[column] is None
                for column in (
                    "waitlisted_at",
                    "left_at",
                    "checked_in_at",
                    "completed_at",
                    "no_show_at",
                    "confirmation_expired_at",
                    "waitlist_expired_at",
                )
            )
        with pytest.raises(IntegrityError) as caught, connection.begin_nested():
            connection.execute(
                text(
                    "INSERT INTO activity_participations "
                    "(activity_id,user_id,status,joined_at,confirmed_at) "
                    "VALUES (:activity,:user,'CONFIRMED',now(),now())"
                ),
                {"activity": pairs[0][0], "user": pairs[0][1]},
            )
        assert caught.value.orig.sqlstate == "23505"
        assert caught.value.orig.diag.constraint_name == "pk_activity_participations"


def test_existing_organizer_participation_in_every_state_is_preserved(
    migration_database,
):
    engine, config = migration_database
    with Session(engine, expire_on_commit=False) as session:
        pairs = [
            seed_legacy_activity(session, status=status.value)
            for status in ParticipationStatus
        ]
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO activity_photos "
                "(id,activity_id,uploader_id,object_key,content_type,size_bytes,created_at) "
                "VALUES (:id,:activity,:user,'legacy/real.jpg','image/jpeg',100,:now)"
            ),
            {
                "id": uuid4(),
                "activity": pairs[0][0],
                "user": pairs[0][1],
                "now": CUTOFF,
            },
        )
        before = snapshot(connection)
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert snapshot(connection) == before


def test_historical_and_cancelled_legacy_activities_get_no_synthetic_participation(
    migration_database,
):
    engine, config = migration_database
    with Session(engine, expire_on_commit=False) as session:
        seed_legacy_activity(session, end_at=CUTOFF - timedelta(microseconds=1))
        seed_legacy_activity(session, end_at=CUTOFF)
        seed_legacy_activity(session, cancelled=True)
        seed_legacy_activity(session, end_at=CUTOFF, cancelled=True)
        seed_legacy_activity(session, end_at=CUTOFF, status="COMPLETED")
        seed_legacy_activity(session, cancelled=True, status="CHECKED_IN")
    with engine.connect() as connection:
        before = snapshot(connection)
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert snapshot(connection) == before


def test_backfill_repeat_and_downgrade_upgrade_preserve_genuine_attendance(
    migration_database,
):
    engine, config = migration_database
    with Session(engine, expire_on_commit=False) as session:
        pairs = [seed_legacy_activity(session) for _ in range(3)]
    command.upgrade(config, REVISION)
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE activity_participations "
                "SET status='CHECKED_IN', checked_in_at=confirmed_at + interval '1 minute' "
                "WHERE activity_id=:activity"
            ),
            {"activity": pairs[1][0]},
        )
        connection.execute(
            text(
                "UPDATE activity_participations SET status='COMPLETED', "
                "checked_in_at=confirmed_at + interval '1 minute', "
                "completed_at=confirmed_at + interval '2 minutes' "
                "WHERE activity_id=:activity"
            ),
            {"activity": pairs[2][0]},
        )
        connection.execute(
            text("UPDATE users SET points_total=points_total+10 WHERE id=:user"),
            {"user": pairs[2][1]},
        )
        before = snapshot(connection)
    # Exercise the actual SQL twice; invoking Alembic at the same head alone
    # would not rerun the migration and would not prove backfill idempotency.
    migration = ScriptDirectory.from_config(config).get_revision(REVISION).module
    for _ in range(2):
        with engine.begin() as connection:
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert snapshot(connection) == before
    command.downgrade(config, PREVIOUS_REVISION)
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == PREVIOUS_REVISION
        )
        assert snapshot(connection) == before
    command.upgrade(config, REVISION)
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == REVISION
        )
        assert snapshot(connection) == before
