from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, create_refresh_token
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import (
    ACTIVITY_CONFIRM_RESPONSE_EXAMPLE,
    ACTIVITY_CREATE_EXAMPLE,
    ActivityRead,
)

NOW = datetime(2030, 8, 8, 4, tzinfo=UTC)
START = NOW + timedelta(hours=12)


def freeze(monkeypatch, now):
    import app.services.activity_management_service as management
    import app.services.activity_service as activities
    import app.services.participation_service as participation

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is not None else now.replace(tzinfo=None)

    for module in (activities, participation, management):
        monkeypatch.setattr(module, "datetime", Clock)


@pytest.fixture
def context(client, db_session, monkeypatch):
    monkeypatch.setenv("ACTIVITY_CONFIRMATION_WINDOW_HOURS", "24")
    get_settings.cache_clear()
    freeze(monkeypatch, NOW)
    users = [
        User(
            email=f"cycle{i}@example.com",
            display_name=f"Cycle{i}",
            password_hash="unused",
        )
        for i in range(6)
    ]
    db_session.add_all(users)
    db_session.commit()
    headers = [
        {"Authorization": f"Bearer {create_access_token(user.id)}"} for user in users
    ]
    response = client.post(
        "/api/v1/activities",
        headers=headers[0],
        json={
            **ACTIVITY_CREATE_EXAMPLE,
            "min_participants": 2,
            "max_participants": 3,
            "start_at": START.isoformat(),
            "end_at": (START + timedelta(hours=2)).isoformat(),
        },
    )
    assert response.status_code == 201
    return UUID(response.json()["id"]), users, headers


def path(context):
    return f"/api/v1/activities/{context[0]}"


def request(client, context, action, user=1):
    method = client.delete if action == "leave" else client.post
    return method(
        path(context) + ("/join" if action == "leave" else f"/{action}"),
        headers=context[2][user],
    )


def stored(db_session, context, user=1):
    return db_session.get(
        ActivityParticipation, (context[0], context[1][user].id), populate_existing=True
    )


@pytest.mark.parametrize("confirmed", [False, True])
def test_leave_retains_cycle_and_rejoin_resets_it(
    client, db_session, context, monkeypatch, confirmed
):
    assert request(client, context, "join").status_code == 201
    if confirmed:
        assert request(client, context, "confirm").status_code == 200
    original = stored(db_session, context)
    original_join = original.joined_at
    original_confirmation = original.confirmed_at
    freeze(monkeypatch, NOW + timedelta(minutes=1))
    response = request(client, context, "leave")
    assert response.status_code == 200
    row = stored(db_session, context)
    assert row.status == "LEFT" and row.left_at is not None
    assert row.joined_at == original_join and row.confirmed_at == original_confirmation
    assert response.json()["current_user_participation"] is None
    assert response.json()["participant_count"] == 0
    assert response.json()["available_slots"] == 3
    assert response.json()["permissions"]["can_join"] is True
    assert not response.json()["permissions"]["can_confirm"]
    assert not response.json()["permissions"]["can_leave"]
    assert request(client, context, "leave").status_code == 409
    left_at = row.left_at
    assert stored(db_session, context).left_at == left_at
    freeze(monkeypatch, NOW + timedelta(minutes=2))
    assert request(client, context, "join").status_code == 201
    row = stored(db_session, context)
    assert row.status == "JOINED" and row.left_at is None and row.confirmed_at is None
    assert row.joined_at > original_join
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 1
    )
    assert request(client, context, "join").json() == {
        "detail": "Already joined this activity"
    }


@pytest.mark.parametrize("block", ["full", "ended", "cancelled"])
def test_rejoin_revalidates_and_does_not_mutate_left_row(
    client, db_session, context, monkeypatch, block
):
    assert request(client, context, "join").status_code == 201
    assert request(client, context, "leave").status_code == 200
    row = stored(db_session, context)
    old_times = (row.joined_at, row.left_at, row.confirmed_at)
    if block == "full":
        for user in (2, 3, 4):
            assert request(client, context, "join", user).status_code == 201
    elif block == "cancelled":
        assert request(client, context, "cancel", 0).status_code == 200
    else:
        freeze(monkeypatch, START + timedelta(hours=2))
    result = request(client, context, "join")
    assert result.status_code == 409
    assert result.json() == {
        "detail": {
            "full": "Activity is full",
            "ended": "Activity has ended",
            "cancelled": "Activity is cancelled",
        }[block]
    }
    row = stored(db_session, context)
    assert (
        row.status == "LEFT"
        and (row.joined_at, row.left_at, row.confirmed_at) == old_times
    )


@pytest.mark.parametrize(
    "offset,success,detail",
    [
        (
            timedelta(hours=-24, microseconds=-1),
            False,
            "Confirmation window has not opened",
        ),
        (timedelta(hours=-24), True, None),
        (timedelta(microseconds=-1), True, None),
        (timedelta(0), False, "Confirmation window has closed"),
        (timedelta(seconds=1), False, "Confirmation window has closed"),
        (timedelta(hours=2), False, "Activity has ended"),
    ],
)
def test_confirmation_exact_window_boundaries(
    client, db_session, context, monkeypatch, offset, success, detail
):
    assert request(client, context, "join").status_code == 201
    freeze(monkeypatch, START + offset)
    before = client.get(path(context), headers=context[2][1]).json()
    assert before["permissions"]["can_confirm"] is success
    response = request(client, context, "confirm")
    assert response.status_code == (200 if success else 409)
    row = stored(db_session, context)
    if success:
        body = response.json()
        assert row.status == body["current_user_participation"]["status"] == "CONFIRMED"
        assert row.confirmed_at.replace(tzinfo=UTC) == START + offset
        assert (
            datetime.fromisoformat(body["current_user_participation"]["confirmed_at"])
            == START + offset
        )
        assert not body["permissions"]["can_confirm"]
        assert body["permissions"]["can_leave"]
        assert body["participant_count"] == 1 and body["available_slots"] == 2
        assert body["checked_in_count"] == 0
        assert body["permissions"]["can_check_in"] is (offset >= timedelta(minutes=-30))
        assert request(client, context, "confirm").json() == {
            "detail": "Already confirmed attendance"
        }
        assert request(client, context, "join").json() == {
            "detail": "Already joined this activity"
        }
    else:
        assert response.json() == {"detail": detail}
        assert row.status == "JOINED" and row.confirmed_at is None


@pytest.mark.parametrize(
    "credential", ["missing", "invalid", "expired", "refresh", "inactive", "unknown"]
)
def test_confirm_requires_valid_access_identity(
    client, db_session, context, credential
):
    user_id = context[1][1].id
    if credential == "missing":
        headers = {}
    else:
        if credential == "inactive":
            context[1][1].is_active = False
            db_session.commit()
        token = {
            "invalid": "bad-token",
            "expired": create_access_token(
                user_id, expires_delta=timedelta(seconds=-1)
            ),
            "refresh": create_refresh_token(user_id),
            "unknown": create_access_token(uuid4()),
        }.get(credential, create_access_token(user_id))
        headers = {"Authorization": f"Bearer {token}"}
    response = client.post(path(context) + "/confirm", headers=headers)
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("activity_id,code", [("not-uuid", 422), (str(uuid4()), 404)])
def test_confirm_unknown_or_invalid_activity(client, context, activity_id, code):
    response = client.post(
        f"/api/v1/activities/{activity_id}/confirm", headers=context[2][1]
    )
    assert response.status_code == code


@pytest.mark.parametrize("caller", ["organizer", "nonmember", "left"])
def test_only_joined_participant_can_confirm(client, context, caller):
    if caller == "left":
        request(client, context, "join")
        request(client, context, "leave")
    response = request(client, context, "confirm", 0 if caller == "organizer" else 1)
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Organizer cannot confirm their own activity"
        if caller == "organizer"
        else "Not participating in this activity"
    }


@pytest.mark.parametrize("unlimited", [False, True])
def test_mixed_states_counts_privacy_and_my_activities(
    client, db_session, context, unlimited
):
    if unlimited:
        assert (
            client.patch(
                path(context),
                headers=context[2][0],
                json={"has_participant_limit": False, "max_participants": None},
            ).status_code
            == 200
        )
    for user in (1, 2, 3):
        assert request(client, context, "join", user).status_code == 201
    assert request(client, context, "confirm", 2).status_code == 200
    assert request(client, context, "leave", 3).status_code == 200
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 3
    )
    for user, expected in [(1, "JOINED"), (2, "CONFIRMED"), (3, None), (4, None)]:
        response = client.get(path(context), headers=context[2][user])
        body = response.json()
        assert body["participant_count"] == 2
        assert body["available_slots"] == (None if unlimited else 1)
        membership = body["current_user_participation"]
        assert (membership["status"] if membership else None) == expected
        if membership:
            assert (membership["confirmed_at"] is not None) is (expected == "CONFIRMED")
        items = client.get(
            "/api/v1/users/me/activities",
            headers=context[2][user],
            params={"relation": "joined"},
        ).json()
        assert len(items) == (1 if expected else 0)
        if items:
            assert items[0]["current_user_participation"] == membership
        assert body["permissions"]["can_confirm"] is (expected == "JOINED")
    anonymous = client.get(path(context)).json()
    assert anonymous["current_user_participation"] is None and not any(
        anonymous["permissions"].values()
    )
    assert "confirmed_at" not in str(anonymous)
    cards = client.get("/api/v1/activities").json()
    assert cards[0]["participant_count"] == 2
    assert "current_user_participation" not in cards[0]


def test_cancellation_preserves_all_states_and_blocks_every_action(
    client, db_session, context
):
    for user in (1, 2, 3):
        request(client, context, "join", user)
    request(client, context, "confirm", 2)
    request(client, context, "leave", 3)
    before = [
        (
            stored(db_session, context, i).status,
            stored(db_session, context, i).confirmed_at,
            stored(db_session, context, i).left_at,
        )
        for i in (1, 2, 3)
    ]
    body = request(client, context, "cancel", 0).json()
    assert body["participant_count"] == 2
    for user in (1, 2, 3):
        for action in ("join", "leave", "confirm"):
            response = request(client, context, action, user)
            assert response.status_code == 409 and response.json() == {
                "detail": "Activity is cancelled"
            }
        detail = client.get(path(context), headers=context[2][user]).json()
        assert not any(detail["permissions"].values())
    after = [
        (
            stored(db_session, context, i).status,
            stored(db_session, context, i).confirmed_at,
            stored(db_session, context, i).left_at,
        )
        for i in (1, 2, 3)
    ]
    assert before == after


@pytest.mark.parametrize("field", ["start_at", "end_at"])
def test_confirmed_members_block_actual_schedule_changes_only(
    client, db_session, context, field
):
    request(client, context, "join")
    original = client.get(path(context)).json()
    assert (
        client.patch(
            path(context), headers=context[2][0], json={field: original[field]}
        ).status_code
        == 200
    )
    request(client, context, "confirm")
    value = START + timedelta(hours=1 if field == "start_at" else 3)
    response = client.patch(
        path(context), headers=context[2][0], json={field: value.isoformat()}
    )
    assert response.status_code == 409
    assert response.json() == {
        "detail": "Cannot change schedule while participants are confirmed"
    }
    assert (
        client.patch(
            path(context),
            headers=context[2][0],
            json={field: original[field], "title": "Same schedule, changed title"},
        ).status_code
        == 200
    )
    request(client, context, "leave")
    assert stored(db_session, context).confirmed_at is not None
    assert (
        client.patch(
            path(context), headers=context[2][0], json={field: value.isoformat()}
        ).status_code
        == 200
    )


def test_capacity_edit_counts_confirmed_but_excludes_left(client, context):
    for user in (1, 2, 3):
        request(client, context, "join", user)
    request(client, context, "confirm", 1)
    response = client.patch(
        path(context), headers=context[2][0], json={"max_participants": 2}
    )
    assert response.status_code == 409
    request(client, context, "leave", 3)
    response = client.patch(
        path(context), headers=context[2][0], json={"max_participants": 2}
    )
    assert response.status_code == 200 and response.json()["participant_count"] == 2
    assert request(client, context, "join", 3).status_code == 409


@pytest.mark.parametrize("hours", [0, -1, 8761, "invalid"])
def test_confirmation_window_setting_rejects_invalid_values(hours):
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            database_url="sqlite://",
            activity_confirmation_window_hours=hours,
        )


def test_window_setting_is_shared_by_metadata_permissions_and_mutation(
    client, context, monkeypatch
):
    request(client, context, "join")
    monkeypatch.setenv("ACTIVITY_CONFIRMATION_WINDOW_HOURS", "2")
    get_settings.cache_clear()
    body = client.get(path(context), headers=context[2][1]).json()
    assert datetime.fromisoformat(body["confirmation_opens_at"]) == START - timedelta(
        hours=2
    )
    assert datetime.fromisoformat(body["confirmation_deadline_at"]) == START
    assert not body["permissions"]["can_confirm"]
    assert request(client, context, "confirm").json() == {
        "detail": "Confirmation window has not opened"
    }
    freeze(monkeypatch, START - timedelta(hours=2))
    assert client.get(path(context), headers=context[2][1]).json()["permissions"][
        "can_confirm"
    ]
    assert request(client, context, "confirm").status_code == 200


@pytest.mark.parametrize(
    "status,left,confirmed",
    [
        ("INVALID", None, None),
        ("CONFIRMED", None, None),
        ("LEFT", None, None),
        ("JOINED", NOW, None),
        ("JOINED", None, NOW),
    ],
)
def test_model_rejects_invalid_lifecycle_rows(
    db_session, context, status, left, confirmed
):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            ActivityParticipation(
                activity_id=context[0],
                user_id=context[1][1].id,
                status=status,
                left_at=left,
                confirmed_at=confirmed,
            )
        )
        db_session.flush()


def test_confirm_failure_rolls_back_status_and_timestamp(
    client, db_session, context, monkeypatch
):
    import app.services.participation_service as service

    request(client, context, "join")

    def fail(*args, **kwargs):
        raise RuntimeError("snapshot failed")

    monkeypatch.setattr(service, "_snapshot", fail)
    with pytest.raises(RuntimeError, match="snapshot failed"):
        request(client, context, "confirm")
    row = stored(db_session, context)
    assert row.status == "JOINED" and row.confirmed_at is None


def test_personalized_lifecycle_lists_preserve_constant_query_counts(
    client, db_session, context
):
    request(client, context, "join")
    request(client, context, "confirm")
    statements = []
    engine = db_session.get_bind()

    def record(_conn, _cursor, statement, _params, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        for relation in ("organized", "joined"):
            statements.clear()
            client.get(
                "/api/v1/users/me/activities",
                headers=context[2][0 if relation == "organized" else 1],
                params={"relation": relation},
            )
            assert len(statements) == 2
        statements.clear()
        client.get("/api/v1/activities")
        assert len(statements) == 1
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_confirm_openapi_auth_errors_metadata_and_complete_example(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/activities/{activity_id}/confirm"]["post"]
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "requestBody" not in operation
    assert {"200", "401", "404", "409", "422"} <= operation["responses"].keys()
    example = operation["responses"]["200"]["content"]["application/json"]["example"]
    assert example == ACTIVITY_CONFIRM_RESPONSE_EXAMPLE
    body = ActivityRead.model_validate(example)
    assert body.current_user_participation.status == "CONFIRMED"
    assert body.current_user_participation.confirmed_at is not None
    assert not body.permissions.can_confirm and not body.permissions.can_check_in


@pytest.mark.parametrize("cancelled", [False, True])
def test_confirmed_membership_remains_in_history_without_future_permissions(
    client, context, monkeypatch, cancelled
):
    request(client, context, "join")
    request(client, context, "confirm")
    if cancelled:
        request(client, context, "cancel", 0)
    freeze(monkeypatch, START + timedelta(hours=2))
    response = client.get(
        "/api/v1/users/me/activities",
        params={"relation": "joined", "scope": "history"},
        headers=context[2][1],
    )
    assert response.status_code == 200 and len(response.json()) == 1
    body = response.json()[0]
    assert body["status"] == ("CANCELLED" if cancelled else "ENDED")
    assert body["current_user_participation"]["status"] == "CONFIRMED"
    assert body["current_user_participation"]["confirmed_at"] is not None
    assert not any(body["permissions"].values())
    assert (
        client.get(
            "/api/v1/users/me/activities",
            params={"relation": "joined", "scope": "upcoming"},
            headers=context[2][1],
        ).json()
        == []
    )


def test_very_early_activity_dates_remain_readable(client, context):
    response = client.post(
        "/api/v1/activities",
        headers=context[2][0],
        json={
            **ACTIVITY_CREATE_EXAMPLE,
            "start_at": "0001-01-01T01:00:00Z",
            "end_at": "0001-01-01T02:00:00Z",
        },
    )
    assert response.status_code == 201
    assert response.json()["confirmation_opens_at"] == "0001-01-01T00:00:00Z"
