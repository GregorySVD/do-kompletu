"""Organizer acceptance tests; geographic authorization is verified in PostgreSQL."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from gallery_data import FakeStorage, image_bytes
from sqlalchemy import event, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.security import create_access_token
from app.main import app
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCreate
from app.services import activity_management_service as management
from app.services import activity_service as activities
from app.services import gallery_service
from app.services import participation_service as participation
from app.services.participation_lifecycle_service import (
    run_participation_lifecycle_sweep,
)
from app.services.photo_storage import get_photo_storage

START = datetime(2030, 8, 8, 16, tzinfo=UTC)
END = START + timedelta(hours=2)
EARLY = START - timedelta(hours=2)
COORDINATES = {"latitude": 52.4232, "longitude": 16.9461, "accuracy_m": 20}


def payload(maximum=2):
    return {
        **ACTIVITY_CREATE_EXAMPLE,
        "start_at": START.isoformat(),
        "end_at": END.isoformat(),
        "min_participants": 2,
        "max_participants": maximum,
        "has_participant_limit": maximum is not None,
    }


@pytest.fixture
def organizers(client, db_session, monkeypatch):
    clock = [EARLY]

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return clock[0] if tz is not None else clock[0].replace(tzinfo=None)

    for module in (activities, management, participation):
        monkeypatch.setattr(module, "datetime", Clock)
    monkeypatch.setattr(gallery_service, "utc_now", lambda: clock[0])
    for name, value in {
        "ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE": "60",
        "ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE": "30",
        "ACTIVITY_CHECK_IN_OPEN_MINUTES_BEFORE": "30",
        "ACTIVITY_CHECK_IN_CLOSE_MINUTES_AFTER": "60",
        "ACTIVITY_CHECK_IN_MAX_ACCURACY_METERS": "100",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    # This suite verifies state/time/HTTP rules only. The paired PostgreSQL
    # suite leaves the real ST_DWithin implementation intact.
    monkeypatch.setattr(participation, "_within_check_in_radius", lambda *_: True)
    users = [
        User(
            email=f"organizer-acceptance-{index}@example.com",
            display_name=f"OrganizerAcceptance{index}",
            password_hash="unused",
        )
        for index in range(5)
    ]
    db_session.add_all(users)
    db_session.commit()
    headers = [
        {"Authorization": f"Bearer {create_access_token(user.id)}"} for user in users
    ]
    storage = FakeStorage()
    app.dependency_overrides[get_photo_storage] = lambda: storage
    yield users, headers, clock, storage
    get_settings.cache_clear()


def create(client, organizers, maximum=2):
    response = client.post(
        "/api/v1/activities", headers=organizers[1][0], json=payload(maximum)
    )
    assert response.status_code == 201
    return response.json()


def action(client, organizers, activity_id, name, user=0, **kwargs):
    method = client.delete if name == "leave" else client.post
    suffix = "join" if name == "leave" else name
    if name == "check-in":
        kwargs.setdefault("json", COORDINATES)
    return method(
        f"/api/v1/activities/{activity_id}/{suffix}",
        headers=organizers[1][user],
        **kwargs,
    )


def detail(client, organizers, activity_id):
    return client.get(
        f"/api/v1/activities/{activity_id}", headers=organizers[1][0]
    ).json()


def stored(session, organizers, activity_id, user=0):
    return session.get(
        ActivityParticipation,
        (UUID(activity_id), organizers[0][user].id),
        populate_existing=True,
    )


@pytest.mark.parametrize("maximum,available", [(10, 9), (2, 1), (None, None)])
def test_creation_returns_real_confirmed_organizer_and_database_counts(
    client, db_session, organizers, maximum, available
):
    body = create(client, organizers, maximum)
    assert body["participant_count"] == 1
    assert body["available_slots"] == available
    assert body["checked_in_count"] == body["waitlist_count"] == 0
    member = body["current_user_participation"]
    assert member["status"] == "CONFIRMED"
    assert datetime.fromisoformat(member["joined_at"]) == EARLY
    assert datetime.fromisoformat(member["confirmed_at"]) == EARLY
    assert all(
        value is None
        for name, value in member.items()
        if name not in {"status", "joined_at", "confirmed_at"}
    )
    assert all(
        not body["permissions"][name]
        for name in ("can_join", "can_leave", "can_confirm", "can_check_in")
    )
    assert body["permissions"]["can_view_gallery"]
    assert not body["permissions"]["can_upload_photo"]
    row = stored(db_session, organizers, body["id"])
    assert row.status == "CONFIRMED" and row.joined_at == row.confirmed_at
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 1
    )
    assert organizers[0][0].points_total == 0


def test_existing_two_person_minimum_is_preserved(client, db_session, organizers):
    response = client.post(
        "/api/v1/activities", headers=organizers[1][0], json=payload(1)
    )
    assert response.status_code == 422
    assert db_session.scalar(select(func.count()).select_from(Activity)) == 0


def test_participation_insert_failure_rolls_back_activity(db_session, organizers):
    attempted = []

    def fail(_mapper, connection, target):
        attempted.append(target.activity_id)
        assert (
            connection.scalar(
                select(Activity.id).where(Activity.id == target.activity_id)
            )
            == target.activity_id
        )
        raise RuntimeError("forced organizer insertion failure")

    event.listen(ActivityParticipation, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="forced organizer insertion failure"):
            activities.create_activity(
                db_session, ActivityCreate.model_validate(payload()), organizers[0][0]
            )
    finally:
        event.remove(ActivityParticipation, "before_insert", fail)
    assert len(attempted) == 1
    assert db_session.scalar(select(func.count()).select_from(Activity)) == 0
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 0
    )


def test_existing_composite_primary_key_prevents_duplicate_organizer(
    client, db_session, organizers
):
    body = create(client, organizers)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            insert(ActivityParticipation).values(
                activity_id=UUID(body["id"]),
                user_id=organizers[0][0].id,
                status="CONFIRMED",
                joined_at=EARLY,
                confirmed_at=EARLY,
            )
        )
    assert stored(db_session, organizers, body["id"]).status == "CONFIRMED"
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 1
    )


@pytest.mark.parametrize("operation", ["join", "leave", "confirm"])
def test_organizer_ordinary_operations_remain_explicitly_forbidden(
    client, db_session, organizers, operation
):
    body = create(client, organizers)
    response = action(client, organizers, body["id"], operation)
    assert response.status_code == 409
    assert "Organizer cannot" in response.json()["detail"]
    assert stored(db_session, organizers, body["id"]).status == "CONFIRMED"
    assert detail(client, organizers, body["id"])["participant_count"] == 1


def test_organizer_cannot_rejoin_even_if_legacy_row_is_left(
    client, db_session, organizers
):
    body = create(client, organizers)
    row = stored(db_session, organizers, body["id"])
    row.status, row.left_at = "LEFT", EARLY
    db_session.commit()
    assert action(client, organizers, body["id"], "join").status_code == 409
    assert stored(db_session, organizers, body["id"]).status == "LEFT"


@pytest.mark.parametrize("minutes", [-31, 60, 120])
def test_organizer_check_in_respects_closed_windows(
    client, db_session, organizers, minutes
):
    body = create(client, organizers)
    organizers[2][0] = START + timedelta(minutes=minutes)
    assert not detail(client, organizers, body["id"])["permissions"]["can_check_in"]
    response = action(client, organizers, body["id"], "check-in")
    assert response.status_code == 409
    assert "Organizer" not in response.json()["detail"]
    row = stored(db_session, organizers, body["id"])
    assert row.status == "CONFIRMED" and row.checked_in_at is None


def test_organizer_check_in_uses_real_membership_and_disables_duplicate(
    client, db_session, organizers
):
    body = create(client, organizers)
    organizers[2][0] = START - timedelta(minutes=30)
    assert detail(client, organizers, body["id"])["permissions"]["can_check_in"]
    response = action(client, organizers, body["id"], "check-in")
    assert response.status_code == 200
    checked = response.json()
    assert checked["current_user_participation"]["status"] == "CHECKED_IN"
    assert checked["checked_in_count"] == checked["participant_count"] == 1
    assert not checked["permissions"]["can_check_in"]
    assert checked["permissions"]["can_view_gallery"]
    assert checked["permissions"]["can_upload_photo"]
    before = stored(db_session, organizers, body["id"]).checked_in_at
    duplicate = action(client, organizers, body["id"], "check-in")
    assert duplicate.status_code == 409
    assert duplicate.json() == {"detail": "Already checked in"}
    assert stored(db_session, organizers, body["id"]).checked_in_at == before


@pytest.mark.parametrize(
    "invalid",
    [
        {"latitude": 52.4, "longitude": 16.9},
        {**COORDINATES, "accuracy_m": 0},
        {**COORDINATES, "accuracy_m": -1},
        {**COORDINATES, "latitude": 91},
        {**COORDINATES, "longitude": -181},
        {**COORDINATES, "extra": True},
    ],
)
def test_organizer_check_in_keeps_request_validation(
    client, db_session, organizers, invalid
):
    body = create(client, organizers)
    organizers[2][0] = START - timedelta(minutes=15)
    assert (
        action(client, organizers, body["id"], "check-in", json=invalid).status_code
        == 422
    )
    assert stored(db_session, organizers, body["id"]).status == "CONFIRMED"


def test_organizer_poor_accuracy_is_rejected_before_spatial_query(
    client, db_session, organizers, monkeypatch
):
    body = create(client, organizers)
    organizers[2][0] = START - timedelta(minutes=15)

    def unexpected(*_):
        pytest.fail("Poor accuracy must be rejected before PostGIS")

    monkeypatch.setattr(participation, "_within_check_in_radius", unexpected)
    response = action(
        client,
        organizers,
        body["id"],
        "check-in",
        json={**COORDINATES, "accuracy_m": 101},
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Location accuracy is insufficient for check-in"
    }
    assert stored(db_session, organizers, body["id"]).status == "CONFIRMED"


def test_organizer_still_requires_confirmed_status(client, db_session, organizers):
    body = create(client, organizers)
    row = stored(db_session, organizers, body["id"])
    row.status, row.confirmed_at = "JOINED", None
    db_session.commit()
    organizers[2][0] = START - timedelta(minutes=15)
    assert not detail(client, organizers, body["id"])["permissions"]["can_check_in"]
    response = action(client, organizers, body["id"], "check-in")
    assert response.status_code == 409
    assert response.json() == {"detail": "Attendance must be confirmed before check-in"}


def test_organizer_gallery_upload_requires_check_in_and_closes_after_72_hours(
    client, organizers
):
    body = create(client, organizers)
    url = f"/api/v1/activities/{body['id']}/photos"

    def upload():
        return client.post(
            url,
            headers=organizers[1][0],
            files={"file": ("organizer.jpg", image_bytes(), "image/jpeg")},
        )

    assert client.get(url, headers=organizers[1][0]).status_code == 200
    assert upload().status_code == 403
    assert not organizers[3].puts
    organizers[2][0] = START - timedelta(minutes=15)
    assert action(client, organizers, body["id"], "check-in").status_code == 200
    for _ in range(3):
        assert upload().status_code == 201
    assert upload().status_code == 409
    organizers[2][0] = END + timedelta(hours=72)
    current = detail(client, organizers, body["id"])
    assert not current["permissions"]["can_view_gallery"]
    assert not current["permissions"]["can_upload_photo"]
    assert client.get(url, headers=organizers[1][0]).status_code == 403
    assert upload().status_code == 403
    assert len(organizers[3].puts) == 3


@pytest.mark.parametrize("checked_in", [False, True])
def test_cancel_preserves_organizer_evidence_and_blocks_check_in_and_upload(
    client, db_session, organizers, checked_in
):
    body = create(client, organizers)
    organizers[2][0] = START - timedelta(minutes=15)
    if checked_in:
        assert action(client, organizers, body["id"], "check-in").status_code == 200
    cancelled = action(client, organizers, body["id"], "cancel")
    assert cancelled.status_code == 200
    current = cancelled.json()
    assert current["status"] == "CANCELLED"
    assert current["participant_count"] == 1
    assert current["checked_in_count"] == int(checked_in)
    assert current["permissions"]["can_view_gallery"]
    assert not current["permissions"]["can_upload_photo"]
    assert not current["permissions"]["can_check_in"]
    assert action(client, organizers, body["id"], "check-in").json() == {
        "detail": "Activity is cancelled"
    }
    url = f"/api/v1/activities/{body['id']}/photos"
    assert client.get(url, headers=organizers[1][0]).status_code == 200
    assert (
        client.post(
            url,
            headers=organizers[1][0],
            files={"file": ("photo.jpg", image_bytes(), "image/jpeg")},
        ).status_code
        == 403
    )
    assert stored(db_session, organizers, body["id"]).status == (
        "CHECKED_IN" if checked_in else "CONFIRMED"
    )


def test_organizer_occupies_one_slot_and_regular_leave_promotes_fifo(
    client, db_session, organizers
):
    body = create(client, organizers)
    first = action(client, organizers, body["id"], "join", user=1)
    assert first.json()["current_user_participation"]["status"] == "JOINED"
    assert first.json()["participant_count"] == 2
    assert first.json()["available_slots"] == 0
    for user in (2, 3):
        organizers[2][0] += timedelta(seconds=1)
        waiting = action(client, organizers, body["id"], "join", user=user)
        assert waiting.json()["current_user_participation"]["status"] == "WAITLISTED"
        assert (
            waiting.json()["current_user_participation"]["waitlist_position"]
            == user - 1
        )
    assert action(client, organizers, body["id"], "leave").status_code == 409
    assert detail(client, organizers, body["id"])["waitlist_count"] == 2
    assert action(client, organizers, body["id"], "leave", user=1).status_code == 200
    assert stored(db_session, organizers, body["id"], 2).status == "JOINED"
    assert stored(db_session, organizers, body["id"], 3).status == "WAITLISTED"
    assert stored(db_session, organizers, body["id"]).status == "CONFIRMED"
    assert detail(client, organizers, body["id"])["participant_count"] == 2


@pytest.mark.parametrize("checked_in", [False, True])
def test_organizer_finalizes_by_normal_attendance_rules_and_reward(
    client, db_session, organizers, checked_in
):
    body = create(client, organizers)
    assert (
        db_session.get(User, organizers[0][0].id, populate_existing=True).points_total
        == 0
    )
    if checked_in:
        organizers[2][0] = START - timedelta(minutes=15)
        assert action(client, organizers, body["id"], "check-in").status_code == 200
        assert (
            db_session.get(
                User, organizers[0][0].id, populate_existing=True
            ).points_total
            == 0
        )
    organizers[2][0] = END
    finalized = action(client, organizers, body["id"], "finalize")
    assert finalized.status_code == 200
    current = finalized.json()
    assert current["current_user_participation"]["status"] == (
        "COMPLETED" if checked_in else "NO_SHOW"
    )
    assert current["participant_count"] == 0
    assert current["checked_in_count"] == int(checked_in)
    assert current["available_slots"] == 2
    assert db_session.get(
        User, organizers[0][0].id, populate_existing=True
    ).points_total == (10 if checked_in else 0)
    assert action(client, organizers, body["id"], "finalize").status_code == 409
    assert db_session.get(
        User, organizers[0][0].id, populate_existing=True
    ).points_total == (10 if checked_in else 0)


def test_worker_expires_normal_joined_but_not_automatic_organizer(
    client, db_session, session_factory, organizers
):
    body = create(client, organizers)
    assert action(client, organizers, body["id"], "join", user=1).status_code == 201
    result = run_participation_lifecycle_sweep(session_factory, now=START)
    assert result.confirmation_expired == 1 and result.failed == 0
    row = stored(db_session, organizers, body["id"])
    assert row.status == "CONFIRMED" and row.confirmation_expired_at is None
    assert (
        stored(db_session, organizers, body["id"], 1).status == "CONFIRMATION_EXPIRED"
    )


def test_my_activities_includes_organizer_once_in_each_applicable_relation(
    client, organizers
):
    body = create(client, organizers)
    for relation in ("organized", "joined"):
        response = client.get(
            "/api/v1/users/me/activities",
            headers=organizers[1][0],
            params={"relation": relation, "scope": "upcoming"},
        )
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == [body["id"]]
        assert response.json()[0]["current_user_participation"]["status"] == "CONFIRMED"
    assert (
        client.get(
            "/api/v1/users/me/activities",
            headers=organizers[1][0],
            params={"relation": "waitlisted"},
        ).json()
        == []
    )


def test_auto_confirmation_preserves_owner_schedule_editing_until_real_attendance(
    client, organizers
):
    body = create(client, organizers)
    url = f"/api/v1/activities/{body['id']}"
    changed_start = START + timedelta(days=1)
    changed_end = END + timedelta(days=1)
    assert (
        client.patch(
            url,
            headers=organizers[1][0],
            json={
                "start_at": changed_start.isoformat(),
                "end_at": changed_end.isoformat(),
            },
        ).status_code
        == 200
    )
    organizers[2][0] = changed_start - timedelta(minutes=15)
    assert action(client, organizers, body["id"], "check-in").status_code == 200
    assert (
        client.patch(
            url,
            headers=organizers[1][0],
            json={"start_at": (changed_start + timedelta(hours=1)).isoformat()},
        ).status_code
        == 409
    )
    assert (
        client.patch(
            url, headers=organizers[1][0], json={"location_name": "Changed venue"}
        ).status_code
        == 409
    )


def test_external_confirmation_still_protects_activity_schedule(client, organizers):
    body = create(client, organizers)
    assert action(client, organizers, body["id"], "join", user=1).status_code == 201
    organizers[2][0] = START - timedelta(minutes=45)
    assert action(client, organizers, body["id"], "confirm", user=1).status_code == 200
    response = client.patch(
        f"/api/v1/activities/{body['id']}",
        headers=organizers[1][0],
        json={"start_at": (START + timedelta(minutes=15)).isoformat()},
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Cannot change schedule while participants are confirmed"
    }
