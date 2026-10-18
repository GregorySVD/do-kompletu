from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, func, select

from app.core.security import create_access_token, create_refresh_token
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityCategoryId

NOW = datetime(2030, 8, 1, 12, tzinfo=UTC)


def freeze_clock(monkeypatch, now):
    import app.services.activity_management_service as management
    import app.services.activity_service as activities
    import app.services.participation_service as participation

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is not None else now.replace(tzinfo=None)

    for module in (management, activities, participation):
        monkeypatch.setattr(module, "datetime", FixedDatetime)


@pytest.fixture
def context(client, db_session, monkeypatch):
    freeze_clock(monkeypatch, NOW)
    users = [
        User(
            email=f"management-{i}@example.com",
            display_name=f"Manager{i}",
            password_hash="unused-in-token-tests",
        )
        for i in range(4)
    ]
    db_session.add_all(users)
    db_session.commit()
    headers = [
        {"Authorization": f"Bearer {create_access_token(user.id)}"} for user in users
    ]
    created = client.post(
        "/api/v1/activities",
        headers=headers[0],
        json={
            **ACTIVITY_CREATE_EXAMPLE,
            "min_participants": 2,
            "max_participants": 4,
        },
    )
    assert created.status_code == 201
    return created.json(), users, headers


def path(context):
    return f"/api/v1/activities/{context[0]['id']}"


def patch(client, context, payload, user=0):
    return client.patch(path(context), json=payload, headers=context[2][user])


def cancel(client, context, user=0):
    return client.post(f"{path(context)}/cancel", headers=context[2][user])


def join(client, context, user=1):
    response = client.post(f"{path(context)}/join", headers=context[2][user])
    assert response.status_code == 201
    return response


@pytest.mark.parametrize("operation", ["patch", "cancel"])
def test_management_requires_authentication(client, context, operation):
    response = (
        client.patch(path(context), json={"title": "New title"})
        if operation == "patch"
        else client.post(f"{path(context)}/cancel")
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("token_kind", ["invalid", "expired", "refresh", "inactive"])
@pytest.mark.parametrize("operation", ["patch", "cancel"])
def test_management_rejects_invalid_credentials(
    client, db_session, context, token_kind, operation
):
    user = context[1][0]
    token = "bad-token"
    if token_kind == "expired":
        token = create_access_token(user.id, expires_delta=timedelta(seconds=-1))
    elif token_kind == "refresh":
        token = create_refresh_token(user.id)
    elif token_kind == "inactive":
        user.is_active = False
        db_session.commit()
        token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}
    response = (
        client.patch(path(context), headers=headers, json={"title": "New title"})
        if operation == "patch"
        else client.post(f"{path(context)}/cancel", headers=headers)
    )
    assert response.status_code == 401


@pytest.mark.parametrize("operation", ["patch", "cancel"])
def test_non_organizer_is_forbidden_without_leaking_owner_identity(
    client, context, operation
):
    response = (
        patch(client, context, {"title": "New title"}, 1)
        if operation == "patch"
        else cancel(client, context, 1)
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Only the organizer can manage this activity"}
    assert client.get(path(context)).json()["title"] == context[0]["title"]


@pytest.mark.parametrize("operation", ["patch", "cancel"])
@pytest.mark.parametrize(
    "identifier, expected", [(str(uuid4()), 404), ("not-a-uuid", 422)]
)
def test_missing_or_malformed_activity(
    client, context, operation, identifier, expected
):
    target = f"/api/v1/activities/{identifier}"
    response = (
        client.patch(target, json={"title": "New title"}, headers=context[2][0])
        if operation == "patch"
        else client.post(f"{target}/cancel", headers=context[2][0])
    )
    assert response.status_code == expected
    if expected == 404:
        assert response.json() == {"detail": "Activity not found"}


def test_title_patch_is_truly_partial_and_keeps_membership(client, db_session, context):
    join(client, context)
    before = client.get(path(context), headers=context[2][0]).json()
    response = patch(client, context, {"title": "  Renamed activity  "})
    assert response.status_code == 200
    assert response.json() == {**before, "title": "Renamed activity"}
    assert response.headers["cache-control"] == "private, no-store"
    db_session.expire_all()
    stored = db_session.get(Activity, UUID(context[0]["id"]))
    assert stored.title == "Renamed activity"
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 1
    )


@pytest.mark.parametrize(
    "payload, expected",
    [
        (
            {"description": "  Updated description for the group.  "},
            {"description": "Updated description for the group."},
        ),
        (
            {"category_id": ActivityCategoryId.MUSIC.value},
            {
                "category": {
                    "id": ActivityCategoryId.MUSIC.value,
                    "name": "Muzyka",
                    "slug": "muzyka",
                }
            },
        ),
        (
            {
                "start_at": "2030-08-09T18:00:00+02:00",
                "end_at": "2030-08-09T20:00:00+02:00",
            },
            {
                "start_at": "2030-08-09T16:00:00Z",
                "end_at": "2030-08-09T18:00:00Z",
                "confirmation_opens_at": "2030-08-08T16:00:00Z",
                "confirmation_deadline_at": "2030-08-09T16:00:00Z",
                "checkin_opens_at": "2030-08-09T15:30:00Z",
                "checkin_closes_at": "2030-08-09T17:00:00Z",
            },
        ),
        ({"end_at": "2030-08-08T19:00:00Z"}, {"end_at": "2030-08-08T19:00:00Z"}),
        (
            {"location_name": "New venue", "address": "New street 5"},
            {"location_name": "New venue", "address": "New street 5"},
        ),
        ({"latitude": 50.1}, {"latitude": 50.1}),
        ({"longitude": 19.2}, {"longitude": 19.2}),
        (
            {"min_participants": 3, "max_participants": 6},
            {"min_participants": 3, "max_participants": 6, "available_slots": 6},
        ),
        (
            {"has_participant_limit": False, "max_participants": None},
            {"max_participants": None, "available_slots": None},
        ),
        (
            {"price_type": "PAID", "price_amount": 25.5},
            {"price_type": "PAID", "price_amount": 25.5, "currency": "PLN"},
        ),
    ],
)
def test_editable_fields_reuse_create_rules_and_preserve_other_fields(
    client, context, payload, expected
):
    before = context[0]
    response = patch(client, context, payload)
    assert response.status_code == 200, response.text
    assert response.json() == {**before, **expected}


def test_paid_to_free_requires_explicit_price_clear(client, context):
    assert (
        patch(client, context, {"price_type": "PAID", "price_amount": 20}).status_code
        == 200
    )
    invalid = patch(client, context, {"price_type": "FREE"})
    assert invalid.status_code == 422
    assert isinstance(invalid.json()["detail"], list)
    response = patch(client, context, {"price_type": "FREE", "price_amount": None})
    assert response.status_code == 200
    assert response.json()["price_amount"] is response.json()["currency"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"title": "x"},
        {"title": "   "},
        {"description": "short"},
        {"organizer_id": str(uuid4())},
        {"id": str(uuid4())},
        {"status": "PUBLISHED"},
        {"cancelled_at": None},
        {"participant_count": 0},
        {"unknown": True},
        {"category_id": str(uuid4())},
        {"latitude": 91},
        {"longitude": -181},
        {"min_participants": 1},
        {"min_participants": 6},
        {"max_participants": 1},
        {"has_participant_limit": False},
        {"max_participants": None},
        {"start_at": "2030-08-10T16:00:00Z"},
        {"end_at": "2030-08-08T15:00:00Z"},
        {"start_at": "2030-08-08T16:00:00"},
        {"end_at": "2030-08-08T18:00:00"},
        {"price_type": "PAID"},
        {"price_amount": 10},
        {"price_amount": -1},
        {"price_type": "PAID", "price_amount": 10.123},
    ],
)
def test_invalid_payload_or_merged_state_is_rejected_atomically(
    client, context, payload
):
    response = patch(client, context, payload)
    assert response.status_code == 422
    assert client.get(path(context), headers=context[2][0]).json() == context[0]


@pytest.mark.parametrize(
    "field",
    [
        "title",
        "description",
        "category_id",
        "start_at",
        "end_at",
        "location_name",
        "address",
        "latitude",
        "longitude",
        "min_participants",
        "has_participant_limit",
        "price_type",
    ],
)
def test_null_is_rejected_for_non_nullable_edit_fields(client, context, field):
    assert patch(client, context, {field: None}).status_code == 422


def test_capacity_changes_preserve_all_members_and_validate_unlimited_transition(
    client, context
):
    for user in (1, 2, 3):
        join(client, context, user)
    rejected = patch(client, context, {"max_participants": 2})
    assert rejected.status_code == 409
    assert rejected.json() == {
        "detail": "Participant limit cannot be below current participant count"
    }
    valid = patch(client, context, {"max_participants": 3})
    assert valid.status_code == 200
    assert valid.json()["participant_count"] == 3
    assert valid.json()["available_slots"] == 0
    unlimited = patch(
        client, context, {"has_participant_limit": False, "max_participants": None}
    )
    assert unlimited.status_code == 200
    assert unlimited.json()["participant_count"] == 3
    assert unlimited.json()["available_slots"] is None
    assert (
        patch(
            client, context, {"has_participant_limit": True, "max_participants": 2}
        ).status_code
        == 409
    )
    limited = patch(
        client, context, {"has_participant_limit": True, "max_participants": 4}
    )
    assert limited.status_code == 200
    assert limited.json()["available_slots"] == 1


@pytest.mark.parametrize(
    "point, editable, cancellable",
    [
        ("before_start", True, True),
        ("at_start", False, True),
        ("ongoing", False, True),
        ("at_end", False, False),
        ("after_end", False, False),
    ],
)
def test_lifecycle_boundaries_permissions_and_cancellation(
    client, context, monkeypatch, point, editable, cancellable
):
    start = datetime.fromisoformat(context[0]["start_at"])
    end = datetime.fromisoformat(context[0]["end_at"])
    now = {
        "before_start": start - timedelta(microseconds=1),
        "at_start": start,
        "ongoing": start + timedelta(hours=1),
        "at_end": end,
        "after_end": end + timedelta(microseconds=1),
    }[point]
    freeze_clock(monkeypatch, now)
    body = client.get(path(context), headers=context[2][0]).json()
    assert body["permissions"]["can_edit"] is editable
    assert body["permissions"]["can_cancel"] is cancellable
    edited = patch(client, context, {"title": "Changed title"})
    assert edited.status_code == (200 if editable else 409)
    cancelled = cancel(client, context)
    assert cancelled.status_code == (200 if cancellable else 409)
    if cancellable:
        assert cancelled.json()["status"] == "CANCELLED"
        assert not any(cancelled.json()["permissions"].values())


def test_cannot_move_start_to_now_or_past_or_reactivate_started_activity(
    client, context, monkeypatch
):
    for value in (NOW, NOW - timedelta(seconds=1)):
        assert (
            patch(client, context, {"start_at": value.isoformat()}).status_code == 422
        )
    freeze_clock(monkeypatch, datetime.fromisoformat(context[0]["start_at"]))
    assert (
        patch(
            client,
            context,
            {"start_at": "2031-08-01T12:00:00Z", "end_at": "2031-08-01T14:00:00Z"},
        ).status_code
        == 409
    )


def test_cancellation_persists_and_preserves_counts_details_and_personal_lists(
    client, db_session, context
):
    join(client, context)
    response = cancel(client, context)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "CANCELLED"
    assert body["cancelled_at"] == "2030-08-01T12:00:00Z"
    assert body["participant_count"] == 1
    assert body["available_slots"] == 3
    assert not any(body["permissions"].values())
    db_session.expire_all()
    stored = db_session.get(Activity, UUID(body["id"]))
    assert stored.cancelled_at.replace(tzinfo=UTC) == NOW
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 1
    )
    anonymous = client.get(path(context)).json()
    member = client.get(path(context), headers=context[2][1]).json()
    outsider = client.get(path(context), headers=context[2][2]).json()
    assert anonymous["status"] == member["status"] == outsider["status"] == "CANCELLED"
    assert (
        anonymous["current_user_participation"]
        is outsider["current_user_participation"]
        is None
    )
    assert member["current_user_participation"]["status"] == "JOINED"
    assert not any(member["permissions"].values())
    assert client.get("/api/v1/activities").json() == []
    for user, relation in [(0, "organized"), (1, "joined")]:
        result = client.get(
            "/api/v1/users/me/activities",
            headers=context[2][user],
            params={"relation": relation, "scope": "upcoming"},
        ).json()
        assert len(result) == 1
        assert result[0]["id"] == body["id"]
        assert result[0]["status"] == "CANCELLED"
    assert (
        client.get(
            "/api/v1/users/me/activities",
            headers=context[2][2],
            params={"relation": "joined"},
        ).json()
        == []
    )


def test_cancelled_lifecycle_is_permanent_and_ended_membership_remains_in_history(
    client, context, monkeypatch
):
    join(client, context)
    assert cancel(client, context).status_code == 200
    repeated = cancel(client, context)
    assert repeated.status_code == 409
    assert repeated.json() == {"detail": "Activity is cancelled"}
    assert patch(client, context, {"title": "New title"}).status_code == 409
    freeze_clock(monkeypatch, datetime.fromisoformat(context[0]["end_at"]))
    history = client.get(
        "/api/v1/users/me/activities",
        headers=context[2][1],
        params={"relation": "joined", "scope": "history"},
    ).json()
    assert len(history) == 1
    assert history[0]["status"] == "CANCELLED"
    assert history[0]["current_user_participation"]["status"] == "JOINED"


def test_cancelled_membership_cannot_join_or_leave_and_counts_never_change(
    client, context
):
    join(client, context)
    assert cancel(client, context).status_code == 200
    for user in (1, 2):
        for method in ("post", "delete"):
            response = getattr(client, method)(
                f"{path(context)}/join", headers=context[2][user]
            )
            assert response.status_code == 409
            assert response.json() == {"detail": "Activity is cancelled"}
    body = client.get(path(context)).json()
    assert body["participant_count"] == 1
    assert body["available_slots"] == 3


def test_discovery_filters_cancelled_before_pagination(client, context):
    assert cancel(client, context).status_code == 200
    created = client.post(
        "/api/v1/activities", headers=context[2][0], json=ACTIVITY_CREATE_EXAMPLE
    )
    assert created.status_code == 201
    result = client.get(
        "/api/v1/activities", params={"limit": 1, "query": "Orlik"}
    ).json()
    assert [item["id"] for item in result] == [created.json()["id"]]


@pytest.mark.parametrize("operation", ["patch", "cancel"])
def test_management_failure_after_flush_rolls_back(
    client, context, monkeypatch, operation
):
    import app.services.activity_management_service as service

    original = service._snapshot
    calls = []

    def fail_after_write(*args):
        calls.append(True)
        if operation == "cancel" or len(calls) == 2:
            raise RuntimeError("Simulated response snapshot failure")
        return original(*args)

    monkeypatch.setattr(service, "_snapshot", fail_after_write)
    with pytest.raises(RuntimeError, match="Simulated response snapshot failure"):
        patch(
            client, context, {"title": "New title"}
        ) if operation == "patch" else cancel(client, context)
    assert client.get(path(context), headers=context[2][0]).json() == context[0]


@pytest.mark.parametrize("operation, expected_selects", [("patch", 4), ("cancel", 3)])
def test_management_response_has_constant_query_count(
    client, db_session, context, operation, expected_selects
):
    for user in (1, 2, 3):
        join(client, context, user)
    statements = []
    engine = db_session.get_bind()

    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        response = (
            patch(client, context, {"title": "New title"})
            if operation == "patch"
            else cancel(client, context)
        )
        assert response.status_code == 200
        assert response.json()["participant_count"] == 3
        assert len(statements) == expected_selects
    finally:
        event.remove(engine, "before_cursor_execute", record)
