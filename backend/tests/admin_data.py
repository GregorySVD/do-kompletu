from datetime import UTC, datetime

from gallery_data import NOW, FakeStorage, seed

from app.core.security import create_access_token
from app.main import app
from app.services import (
    activity_management_service,
    activity_service,
    admin_service,
    gallery_service,
)
from app.services.photo_storage import get_photo_storage


def seed_admin(session, monkeypatch):
    activity, users = seed(session)
    users[3].is_admin = True
    users[1].points_total = 37
    session.commit()
    storage, clock = FakeStorage(), [NOW]

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=UTC):
            return clock[0].astimezone(tz)

    for module in (activity_management_service, activity_service, admin_service):
        monkeypatch.setattr(module, "datetime", FrozenDatetime)
    monkeypatch.setattr(gallery_service, "utc_now", lambda: clock[0])
    app.dependency_overrides[get_photo_storage] = lambda: storage
    headers = [{"Authorization": f"Bearer {create_access_token(u.id)}"} for u in users]
    return activity, users, storage, clock, headers


def photo_path(context):
    return f"/api/v1/activities/{context[0].id}/photos"
