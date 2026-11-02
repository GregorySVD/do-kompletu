import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from gallery_data import NOW, seed
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings

pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


def test_admin_migration_0011_0012_0011_0012_defaults_constraints_preservation(
    monkeypatch,
):
    source = make_url(os.environ["POSTGRES_TEST_DATABASE_URL"])
    name = "dk_admin_migration_" + uuid4().hex
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
        command.upgrade(config, "20261030_0011")
        with Session(engine, expire_on_commit=False) as session:
            activity, users = seed(session, legacy_users=True)
            activity_id, user_id = activity.id, users[1].id
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO activity_photos (id,activity_id,uploader_id,object_key,content_type,size_bytes,created_at) "
                    "VALUES (:id,:activity,:user,'migration/photo.jpg','image/jpeg',100,:now)"
                ),
                {"id": uuid4(), "activity": activity_id, "user": user_id, "now": NOW},
            )

        def snapshot(connection):
            return {
                table: connection.execute(
                    text(f"SELECT * FROM {table} ORDER BY 1, 2")
                ).all()
                for table in (
                    "users",
                    "activities",
                    "activity_participations",
                    "activity_photos",
                )
            }

        with engine.connect() as connection:
            before = snapshot(connection)
        command.upgrade(config, "20261031_0012")
        with engine.begin() as connection:
            column = next(
                c
                for c in inspect(connection).get_columns("users")
                if c["name"] == "is_admin"
            )
            assert not column["nullable"] and str(column["type"]) == "BOOLEAN"
            assert column["default"] == "false"
            assert (
                connection.execute(text("SELECT is_admin FROM users")).scalars().all()
                == [False] * 4
            )
            # Explicit NULL is rejected; omitted flag gets the server default.
            with pytest.raises(IntegrityError), connection.begin_nested():
                connection.execute(
                    text("UPDATE users SET is_admin = NULL WHERE id = :id"),
                    {"id": user_id},
                )
            connection.execute(
                text(
                    "INSERT INTO users (id,email,password_hash,display_name,points_total,is_active,created_at) "
                    "VALUES (:id,'migration-default@example.com','unused','DefaultUser',0,true,:now)"
                ),
                {"id": uuid4(), "now": NOW},
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT is_admin FROM users WHERE email='migration-default@example.com'"
                    )
                )
                is False
            )
            connection.execute(
                text("DELETE FROM users WHERE email='migration-default@example.com'")
            )
            connection.execute(
                text("UPDATE users SET is_admin=true WHERE id=:id"), {"id": user_id}
            )
            assert (
                connection.scalar(
                    text("SELECT is_admin FROM users WHERE id=:id"), {"id": user_id}
                )
                is True
            )
            after = snapshot(connection)
            assert [tuple(r[:-1]) for r in after["users"]] == [
                tuple(r) for r in before["users"]
            ]
            for table in before.keys() - {"users"}:
                assert after[table] == before[table]
        command.downgrade(config, "20261030_0011")
        with engine.connect() as connection:
            assert "is_admin" not in {
                c["name"] for c in inspect(connection).get_columns("users")
            }
            assert snapshot(connection) == before
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261030_0011"
            )
        command.upgrade(config, "20261031_0012")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261031_0012"
            )
            assert not connection.scalar(
                text("SELECT EXISTS (SELECT 1 FROM users WHERE is_admin)")
            )
            assert connection.scalar(text("SELECT count(*) FROM activity_photos")) == 1
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
