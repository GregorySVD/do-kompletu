from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

from PIL import Image

from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.services.activity_service import _location_value
from app.services.photo_storage import PhotoStorageError

END = datetime(2030, 8, 8, 18, tzinfo=UTC)
NOW = END - timedelta(hours=1)


def assert_only_gallery_permissions(permissions, *, view=True, upload=False):
    assert permissions == {
        key: view
        if key == "can_view_gallery"
        else upload
        if key == "can_upload_photo"
        else False
        for key in permissions
    }


def image_bytes(format="JPEG"):
    output = BytesIO()
    Image.new("RGB", (8, 8), "blue").save(output, format=format)
    return output.getvalue()


class FakeStorage:
    def __init__(self):
        self.objects = {}
        self.puts = []
        self.deletes = []
        self.signs = []
        self.fail_put = self.fail_delete = self.fail_sign = False

    def put(self, key, data, content_type):
        self.puts.append((key, content_type))
        if self.fail_put:
            raise PhotoStorageError("simulated upload failure")
        self.objects[key] = data

    def delete(self, key):
        self.deletes.append(key)
        if self.fail_delete:
            raise PhotoStorageError("simulated deletion failure")
        self.objects.pop(key, None)

    def presigned_get_url(self, key, ttl_seconds):
        if self.fail_sign:
            raise PhotoStorageError("simulated signing failure")
        self.signs.append((key, ttl_seconds))
        return f"https://storage.invalid/{key}?signed={len(self.signs)}"


def seed(session):
    suffix = uuid4().hex
    users = [
        User(
            email=f"gallery-{suffix}-{i}@example.com",
            display_name=f"Gallery{suffix}{i}",
            password_hash="private",
        )
        for i in range(4)
    ]
    session.add_all(users)
    session.flush()
    activity = Activity(
        organizer_id=users[0].id,
        title="Private gallery",
        description="Checked in photos",
        category="gaming",
        start_at=END - timedelta(hours=2),
        end_at=END,
        location_name="Venue",
        address="Address",
        location=_location_value(session, 52.4, 16.9),
        min_participants=2,
        max_participants=4,
        price_type="FREE",
    )
    session.add(activity)
    session.flush()
    for user in users[1:3]:
        set_status(session, activity.id, user.id, "CHECKED_IN")
    session.commit()
    return activity, users


def set_status(session, activity_id, user_id, status):
    row = session.get(ActivityParticipation, (activity_id, user_id))
    if row is None:
        row = ActivityParticipation(activity_id=activity_id, user_id=user_id)
        session.add(row)
    row.status = status
    row.joined_at = (
        None
        if status in {"WAITLISTED", "WAITLIST_EXPIRED"}
        else NOW - timedelta(hours=1)
    )
    row.waitlisted_at = (
        NOW - timedelta(hours=2)
        if status in {"WAITLISTED", "WAITLIST_EXPIRED"}
        else None
    )
    row.confirmed_at = (
        NOW - timedelta(minutes=50)
        if status in {"CONFIRMED", "CHECKED_IN", "COMPLETED"}
        else None
    )
    row.checked_in_at = (
        NOW - timedelta(minutes=10) if status in {"CHECKED_IN", "COMPLETED"} else None
    )
    row.completed_at = END if status == "COMPLETED" else None
    row.no_show_at = END if status == "NO_SHOW" else None
    row.left_at = NOW if status == "LEFT" else None
    row.confirmation_expired_at = NOW if status == "CONFIRMATION_EXPIRED" else None
    row.waitlist_expired_at = NOW if status == "WAITLIST_EXPIRED" else None
    session.flush()
    return row
