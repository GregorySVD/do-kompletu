from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, create_refresh_token
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE


@pytest.fixture
def activity_context(client, db_session):
    users = [
        User(
            email=f"member-{index}@example.com",
            display_name=f"Member {index}",
            password_hash="unused-in-token-tests",
        )
        for index in range(5)
    ]
    db_session.add_all(users)
    db_session.commit()
    headers = [
        {"Authorization": f"Bearer {create_access_token(user.id)}"} for user in users
    ]
    response = client.post(
        "/api/v1/activities",
        headers=headers[0],
        json={**ACTIVITY_CREATE_EXAMPLE, "min_participants": 2, "max_participants": 2},
    )
    assert response.status_code == 201
    return response.json(), users, headers


def detail_path(context):
    return f"/api/v1/activities/{context[0]['id']}"


def join(client, context, user=1):
    return client.post(f"{detail_path(context)}/join", headers=context[2][user])


def leave(client, context, user=1):
    return client.delete(f"{detail_path(context)}/join", headers=context[2][user])


def test_join_persists_membership_and_updates_detail_and_list(
    client, db_session, activity_context
):
    response = join(client, activity_context)
    assert response.status_code == 201
    body = response.json()
    assert body["participant_count"] == 1
    assert body["available_slots"] == 1
    assert body["checked_in_count"] == body["waitlist_count"] == 0
    assert body["current_user_participation"]["status"] == "JOINED"
    joined_at = datetime.fromisoformat(body["current_user_participation"]["joined_at"])
    assert joined_at.tzinfo is not None
    assert body["permissions"]["can_join"] is False
    assert body["permissions"]["can_leave"] is True
    stored = db_session.get(
        ActivityParticipation, (UUID(body["id"]), activity_context[1][1].id)
    )
    assert stored is not None
    assert stored.joined_at.replace(tzinfo=UTC) == joined_at
    detail = client.get(detail_path(activity_context), headers=activity_context[2][1])
    assert detail.json() == body
    card = client.get("/api/v1/activities").json()[0]
    assert card["participant_count"] == 1
    assert card["available_slots"] == 1
    assert "current_user_participation" not in card
    assert "private" in detail.headers["cache-control"]
    assert "no-store" in detail.headers["cache-control"]
    assert "Authorization" in detail.headers["vary"]


def test_duplicate_join_returns_conflict_without_changing_counts(
    client, activity_context
):
    assert join(client, activity_context).status_code == 201
    response = join(client, activity_context)
    assert response.status_code == 409
    assert response.json() == {"detail": "Already joined this activity"}
    assert client.get(detail_path(activity_context)).json()["participant_count"] == 1


@pytest.mark.parametrize("method", ["post", "delete"])
def test_membership_requires_authentication(client, activity_context, method):
    response = getattr(client, method)(f"{detail_path(activity_context)}/join")
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("method", ["post", "delete", "get"])
def test_unknown_activity(client, activity_context, method):
    path = f"/api/v1/activities/{uuid4()}"
    if method != "get":
        path += "/join"
    response = getattr(client, method)(path, headers=activity_context[2][1])
    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


@pytest.mark.parametrize("method", ["post", "delete", "get"])
def test_malformed_activity_id(client, activity_context, method):
    path = "/api/v1/activities/not-a-uuid" + ("" if method == "get" else "/join")
    assert (
        getattr(client, method)(path, headers=activity_context[2][1]).status_code == 422
    )


def test_full_activity_permissions_and_duplicate_precedence(client, activity_context):
    assert join(client, activity_context, 1).status_code == 201
    assert join(client, activity_context, 2).status_code == 201
    assert join(client, activity_context, 1).json() == {
        "detail": "Already joined this activity"
    }
    response = join(client, activity_context, 3)
    assert response.status_code == 409
    assert response.json() == {"detail": "Activity is full"}
    outsider = client.get(
        detail_path(activity_context), headers=activity_context[2][3]
    ).json()
    assert outsider["participant_count"] == 2
    assert outsider["available_slots"] == 0
    assert outsider["permissions"]["can_join"] is False
    participant = client.get(
        detail_path(activity_context), headers=activity_context[2][1]
    ).json()
    assert participant["permissions"]["can_leave"] is True
    assert leave(client, activity_context, 1).status_code == 200
    assert join(client, activity_context, 3).status_code == 201


def test_unlimited_activity_has_no_capacity_ceiling(
    client, db_session, activity_context
):
    activity = db_session.get(Activity, UUID(activity_context[0]["id"]))
    activity.max_participants = None
    db_session.commit()
    for user in range(1, 5):
        response = join(client, activity_context, user)
        assert response.status_code == 201
        assert response.json()["participant_count"] == user
        assert response.json()["available_slots"] is None
    assert client.get(detail_path(activity_context)).json()["available_slots"] is None
    assert client.get("/api/v1/activities").json()[0]["available_slots"] is None


def test_leave_removes_membership_repeat_is_conflict_and_rejoin_works(
    client, db_session, activity_context
):
    assert join(client, activity_context).status_code == 201
    assert join(client, activity_context, 2).status_code == 201
    response = leave(client, activity_context)
    assert response.status_code == 200
    body = response.json()
    assert body["participant_count"] == 1
    assert body["available_slots"] == 1
    assert body["current_user_participation"] is None
    assert body["permissions"]["can_join"] is True
    assert body["permissions"]["can_leave"] is False
    assert (
        db_session.get(
            ActivityParticipation, (UUID(body["id"]), activity_context[1][1].id)
        )
        is None
    )
    repeat = leave(client, activity_context)
    assert repeat.status_code == 409
    assert repeat.json() == {"detail": "Not participating in this activity"}
    assert client.get("/api/v1/activities").json()[0]["participant_count"] == 1
    assert join(client, activity_context).status_code == 201


def test_leave_without_membership(client, activity_context):
    response = leave(client, activity_context)
    assert response.status_code == 409
    assert response.json() == {"detail": "Not participating in this activity"}
    assert client.get(detail_path(activity_context)).json()["participant_count"] == 0


def test_anonymous_and_other_user_do_not_receive_participant_state(
    client, activity_context
):
    assert join(client, activity_context).status_code == 201
    anonymous = client.get(detail_path(activity_context)).json()
    outsider = client.get(
        detail_path(activity_context), headers=activity_context[2][2]
    ).json()
    assert anonymous["participant_count"] == outsider["participant_count"] == 1
    assert anonymous["current_user_participation"] is None
    assert outsider["current_user_participation"] is None
    assert not any(anonymous["permissions"].values())
    assert outsider["permissions"]["can_join"] is True
    assert outsider["permissions"]["can_leave"] is False
    assert not any(
        value for key, value in outsider["permissions"].items() if key != "can_join"
    )
    assert "member-" not in str(anonymous)


def test_organizer_is_separate_from_membership(client, activity_context):
    assert activity_context[0]["participant_count"] == 0
    assert activity_context[0]["current_user_participation"] is None
    for response in [
        join(client, activity_context, 0),
        leave(client, activity_context, 0),
    ]:
        assert response.status_code == 409
        assert response.json() == {
            "detail": "Organizer cannot join or leave their own activity"
        }
    body = client.get(
        detail_path(activity_context), headers=activity_context[2][0]
    ).json()
    assert body["participant_count"] == 0
    assert body["available_slots"] == 2
    assert body["permissions"]["can_edit"] is True
    assert body["permissions"]["can_cancel"] is True
    assert not any(
        value
        for key, value in body["permissions"].items()
        if key not in {"can_edit", "can_cancel"}
    )


@pytest.mark.parametrize("elapsed", [False, True])
def test_lifecycle_boundary(client, db_session, activity_context, monkeypatch, elapsed):
    import app.services.activity_service as activities
    import app.services.participation_service as participation

    assert join(client, activity_context, 1).status_code == 201
    now = datetime.now(UTC)
    activity = db_session.get(Activity, UUID(activity_context[0]["id"]))
    activity.start_at = now - timedelta(hours=1)
    activity.end_at = now if elapsed else now + timedelta(hours=1)
    db_session.commit()

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is not None else now.replace(tzinfo=None)

    monkeypatch.setattr(activities, "datetime", FixedDatetime)
    monkeypatch.setattr(participation, "datetime", FixedDatetime)
    member = client.get(
        detail_path(activity_context), headers=activity_context[2][1]
    ).json()
    outsider = client.get(
        detail_path(activity_context), headers=activity_context[2][2]
    ).json()
    assert member["status"] == ("ENDED" if elapsed else "ONGOING")
    assert member["current_user_participation"]["status"] == "JOINED"
    assert member["permissions"]["can_leave"] is not elapsed
    assert outsider["permissions"]["can_join"] is not elapsed
    joined = join(client, activity_context, 2)
    left = leave(client, activity_context, 1)
    assert joined.status_code == (409 if elapsed else 201)
    assert left.status_code == (409 if elapsed else 200)
    if elapsed:
        assert joined.json() == left.json() == {"detail": "Activity has ended"}
        assert (
            client.get(detail_path(activity_context)).json()["participant_count"] == 1
        )


@pytest.mark.parametrize(
    "credential",
    ["invalid", "expired", "refresh", "missing-user", "inactive", "basic", "empty"],
)
@pytest.mark.parametrize("method", ["get", "post", "delete"])
def test_invalid_supplied_credentials_are_not_anonymous(
    client, db_session, activity_context, credential, method
):
    user_id = activity_context[1][1].id
    if credential == "expired":
        token = create_access_token(user_id, expires_delta=timedelta(seconds=-1))
    elif credential == "refresh":
        token = create_refresh_token(user_id)
    elif credential == "missing-user":
        token = create_access_token(uuid4())
    elif credential == "inactive":
        activity_context[1][1].is_active = False
        db_session.commit()
        token = create_access_token(user_id)
    else:
        token = "bad-token"
    header = f"Bearer {token}"
    if credential == "basic":
        header = "Basic dXNlcjpwYXNz"
    elif credential == "empty":
        header = "Bearer "
    path = detail_path(activity_context) + ("" if method == "get" else "/join")
    response = getattr(client, method)(path, headers={"Authorization": header})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_database_prevents_duplicate_membership(client, db_session, activity_context):
    assert join(client, activity_context).status_code == 201
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            ActivityParticipation(
                activity_id=UUID(activity_context[0]["id"]),
                user_id=activity_context[1][1].id,
            )
        )
        db_session.flush()
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 1
    )


@pytest.mark.parametrize("missing", ["user", "activity"])
def test_database_requires_existing_foreign_keys(db_session, activity_context, missing):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            ActivityParticipation(
                activity_id=uuid4()
                if missing == "activity"
                else UUID(activity_context[0]["id"]),
                user_id=uuid4() if missing == "user" else activity_context[1][1].id,
            )
        )
        db_session.flush()


@pytest.mark.parametrize("deleted", ["user", "activity"])
def test_database_cascades_membership_cleanup(
    client, db_session, activity_context, deleted
):
    assert join(client, activity_context).status_code == 201
    statement = (
        delete(Activity).where(Activity.id == UUID(activity_context[0]["id"]))
        if deleted == "activity"
        else delete(User).where(User.id == activity_context[1][1].id)
    )
    db_session.execute(statement)
    db_session.commit()
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 0
    )


def test_list_counts_are_per_activity_and_survive_pagination(client, activity_context):
    assert join(client, activity_context).status_code == 201
    created = client.post(
        "/api/v1/activities",
        headers=activity_context[2][0],
        json={
            **ACTIVITY_CREATE_EXAMPLE,
            "start_at": "2031-01-01T12:00:00Z",
            "end_at": "2031-01-01T13:00:00Z",
        },
    )
    assert created.status_code == 201
    cards = client.get("/api/v1/activities").json()
    assert [card["participant_count"] for card in cards] == [1, 0]
    assert (
        client.get("/api/v1/activities", params={"offset": 1, "limit": 1}).json()[0][
            "participant_count"
        ]
        == 0
    )


@pytest.mark.parametrize("method", ["post", "delete"])
def test_failed_membership_transaction_rolls_back(
    client, activity_context, monkeypatch, method
):
    import app.services.participation_service as service

    if method == "delete":
        assert join(client, activity_context).status_code == 201

    def fail_snapshot(*args, **kwargs):
        raise RuntimeError("Simulated failure after membership flush")

    monkeypatch.setattr(service, "_snapshot", fail_snapshot)
    with pytest.raises(RuntimeError, match="Simulated failure"):
        getattr(client, method)(
            f"{detail_path(activity_context)}/join", headers=activity_context[2][1]
        )

    body = client.get(
        detail_path(activity_context), headers=activity_context[2][1]
    ).json()
    assert body["participant_count"] == (1 if method == "delete" else 0)
    assert (body["current_user_participation"] is not None) is (method == "delete")
