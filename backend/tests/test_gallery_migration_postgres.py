import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from gallery_data import NOW, seed
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import get_settings
from app.models.activity_photo import ActivityPhoto

pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


def test_gallery_migration_cycle_constraints_and_preservation(monkeypatch):
    source = make_url(os.environ["POSTGRES_TEST_DATABASE_URL"])
    name = "dk_gallery_migration_" + uuid4().hex
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
        command.upgrade(config, "20261019_0010")
        with Session(engine, expire_on_commit=False) as session:
            activity, users = seed(session)
            activity_id, user_id = activity.id, users[1].id
        with engine.connect() as connection:
            before = {
                table: connection.execute(
                    text(f"SELECT * FROM {table} ORDER BY 1, 2")
                ).all()
                for table in ("users", "activities", "activity_participations")
            }
        command.upgrade(config, "20261030_0011")
        with engine.connect() as connection:
            inspector = inspect(connection)
            columns = {c["name"]: c for c in inspector.get_columns("activity_photos")}
            assert set(columns) == {
                "id",
                "activity_id",
                "uploader_id",
                "object_key",
                "content_type",
                "size_bytes",
                "created_at",
            }
            assert all(not c["nullable"] for c in columns.values())
            assert columns["created_at"]["type"].timezone
            assert {i["name"] for i in inspector.get_indexes("activity_photos")} >= {
                "ix_activity_photos_activity_uploader",
                "ix_activity_photos_uploader_id",
            }
            assert all(
                fk["options"]["ondelete"] == "RESTRICT"
                for fk in inspector.get_foreign_keys("activity_photos")
            )
        base = {
            "activity_id": activity_id,
            "uploader_id": user_id,
            "object_key": "unique/photo.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 100,
            "created_at": NOW,
        }
        with Session(engine) as session:
            session.add(ActivityPhoto(**base))
            session.commit()
            for changes in (
                {},
                {"size_bytes": 0},
                {"size_bytes": 10485761},
                {"content_type": "image/svg+xml"},
                {"uploader_id": uuid4()},
                {"activity_id": uuid4()},
            ):
                with pytest.raises(IntegrityError), session.begin_nested():
                    session.add(
                        ActivityPhoto(
                            **{
                                **base,
                                "object_key": uuid4().hex
                                if changes
                                else base["object_key"],
                                **changes,
                            }
                        )
                    )
                    session.flush()
            assert len(session.scalars(select(ActivityPhoto)).all()) == 1
        command.downgrade(config, "20261019_0010")
        with engine.connect() as connection:
            assert not inspect(connection).has_table("activity_photos")
            for table, rows in before.items():
                assert (
                    connection.execute(
                        text(f"SELECT * FROM {table} ORDER BY 1, 2")
                    ).all()
                    == rows
                )
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261019_0010"
            )
        command.upgrade(config, "20261030_0011")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM activity_photos")) == 0
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "20261030_0011"
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
