"""Real PostgreSQL lock contention. SQLite tests do not prove this behavior."""

import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from io import BytesIO

import pytest
import test_activity_management_postgres as pg_data
from gallery_data import END, NOW, FakeStorage, image_bytes, seed
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import Session
from test_activity_management_postgres import wait_for_lock_waiters

from app.models.activity import Activity
from app.models.activity_photo import ActivityPhoto
from app.models.user import User
from app.services import gallery_service as gallery
from app.services.activity_service import get_activity_for_update

pg_engine = pg_data.pg_engine

pytestmark = pytest.mark.skipif(
    os.getenv("POSTGRES_TEST_DATABASE_URL") is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


@pytest.fixture
def pg_gallery(pg_engine):
    with Session(pg_engine, expire_on_commit=False) as session:
        activity, users = seed(session)
        activity_id, user_ids = activity.id, [u.id for u in users]
    try:
        yield activity_id, user_ids, FakeStorage()
    finally:
        with pg_engine.begin() as connection:
            connection.execute(
                delete(ActivityPhoto).where(ActivityPhoto.activity_id == activity_id)
            )
            connection.execute(delete(Activity).where(Activity.id == activity_id))
            connection.execute(delete(User).where(User.id.in_(user_ids)))


def upload(engine, context, user, clock=lambda: NOW):
    with Session(engine, expire_on_commit=False, autoflush=False) as session:
        session.execute(
            text("SELECT set_config('application_name', :name, true)"),
            {"name": f"gallery-{context[0]}"},
        )
        try:
            gallery.upload_photo(
                session,
                context[0],
                context[1][user],
                BytesIO(image_bytes()),
                "image/jpeg",
                context[2],
                clock=clock,
            )
            return 201
        except gallery.GalleryError as exc:
            return exc.status_code


@pytest.mark.parametrize(
    "initial,users,expected",
    [
        (2, (1, 1), [201, 409]),
        (3, (1, 1), [409, 409]),
        (2, (1, 2), [201, 201]),
    ],
)
def test_concurrent_uploads_respect_independent_max_three(
    pg_engine, pg_gallery, initial, users, expected
):
    for user in set(users):
        for _ in range(initial):
            assert upload(pg_engine, pg_gallery, user) == 201
    barrier = threading.Barrier(3)

    def contender(user):
        barrier.wait(timeout=10)
        return upload(pg_engine, pg_gallery, user)

    with ThreadPoolExecutor(max_workers=2) as pool, Session(pg_engine) as lock:
        get_activity_for_update(lock, pg_gallery[0])
        futures = [pool.submit(contender, user) for user in users]
        try:
            barrier.wait(timeout=10)
            wait_for_lock_waiters(pg_engine, f"gallery-{pg_gallery[0]}", 2)
        finally:
            lock.commit()
        assert sorted(f.result(timeout=15) for f in futures) == expected
    with Session(pg_engine) as session:
        for user in set(users):
            total = session.scalar(
                select(func.count())
                .select_from(ActivityPhoto)
                .where(
                    ActivityPhoto.activity_id == pg_gallery[0],
                    ActivityPhoto.uploader_id == pg_gallery[1][user],
                )
            )
            assert total == 3


@pytest.mark.parametrize("change", ["closure", "cancel"])
def test_authorization_uses_fresh_time_and_state_after_parent_lock(
    pg_engine, pg_gallery, change
):
    now = [NOW]
    with ThreadPoolExecutor(max_workers=1) as pool, Session(pg_engine) as lock:
        activity = get_activity_for_update(lock, pg_gallery[0])
        future = pool.submit(upload, pg_engine, pg_gallery, 1, lambda: now[0])
        try:
            wait_for_lock_waiters(pg_engine, f"gallery-{pg_gallery[0]}", 1)
            if change == "closure":
                now[0] = END + timedelta(hours=72)  # No time-based sleep.
            else:
                activity.cancelled_at = NOW
        finally:
            lock.commit()
        assert future.result(timeout=15) == 403
    assert not pg_gallery[2].puts
    with Session(pg_engine) as session:
        assert not session.scalar(
            select(ActivityPhoto.id).where(ActivityPhoto.activity_id == pg_gallery[0])
        )
