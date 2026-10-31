from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from gallery_data import assert_only_gallery_permissions
from sqlalchemy import delete, event, select
from sqlalchemy.exc import IntegrityError
from test_participation_lifecycle import freeze

from app.core.security import create_access_token, create_refresh_token
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import (
    ACTIVITY_CREATE_EXAMPLE,
    ACTIVITY_FINALIZE_RESPONSE_EXAMPLE,
    ActivityRead,
)
from app.services import activity_management_service as management
from app.services import participation_service as participation
from app.services.participation_rules import COMPLETED_ACTIVITY_POINTS

START = datetime(2030, 8, 8, 16, tzinfo=UTC)
END = START + timedelta(hours=2)


@pytest.fixture
def context(client, db_session, monkeypatch):
    freeze(monkeypatch, START - timedelta(minutes=15))
    # Spatial correctness is separately established by the real PostGIS suite.
    monkeypatch.setattr(participation, "_within_check_in_radius", lambda *args: True)
    users = [
        User(
            email=f"outcome{i}@example.com",
            display_name=f"Outcome{i}",
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
        json={**ACTIVITY_CREATE_EXAMPLE, "min_participants": 2, "max_participants": 6},
    )
    assert response.status_code == 201
    activity_id = UUID(response.json()["id"])
    base = f"/api/v1/activities/{activity_id}"
    for i in (1, 2, 3, 4):
        assert client.post(base + "/join", headers=headers[i]).status_code == 201
    for i in (2, 3):
        assert client.post(base + "/confirm", headers=headers[i]).status_code == 200
    assert (
        client.post(
            base + "/check-in",
            headers=headers[3],
            json={"latitude": 52.4232, "longitude": 16.9461, "accuracy_m": 20},
        ).status_code
        == 200
    )
    assert client.delete(base + "/join", headers=headers[4]).status_code == 200
    return activity_id, users, headers


def path(context):
    return f"/api/v1/activities/{context[0]}"


def finalize(client, context, user=0):
    return client.post(path(context) + "/finalize", headers=context[2][user])


def rows(db_session, context):
    return {
        row.user_id: row
        for row in db_session.scalars(
            select(ActivityParticipation)
            .where(ActivityParticipation.activity_id == context[0])
            .execution_options(populate_existing=True)
        )
    }


def snapshot(db_session, context):
    return {
        user: (
            row.status,
            row.joined_at,
            row.confirmed_at,
            row.checked_in_at,
            row.left_at,
            row.completed_at,
            row.no_show_at,
        )
        for user, row in rows(db_session, context).items()
    }


def test_finalize_all_outcomes_preserves_evidence_and_repeated_request_is_409(
    client, db_session, context, monkeypatch
):
    before = snapshot(db_session, context)
    freeze(monkeypatch, END)
    assert client.get(path(context), headers=context[2][0]).json()["permissions"][
        "can_finalize"
    ]
    response = finalize(client, context)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ENDED" and body["current_user_participation"] is None
    assert body["participant_count"] == 0 and body["available_slots"] == 6
    assert body["checked_in_count"] == 1 and body["waitlist_count"] == 0
    assert_only_gallery_permissions(body["permissions"])
    assert response.headers["cache-control"] == "private, no-store"
    current = rows(db_session, context)
    for i, state in [(1, "NO_SHOW"), (2, "NO_SHOW"), (3, "COMPLETED"), (4, "LEFT")]:
        row = current[context[1][i].id]
        assert row.status == state
        assert (
            row.joined_at,
            row.confirmed_at,
            row.checked_in_at,
            row.left_at,
        ) == before[row.user_id][1:5]
        if state in {"NO_SHOW", "COMPLETED"}:
            stamp = row.no_show_at if state == "NO_SHOW" else row.completed_at
            assert stamp.replace(tzinfo=UTC) == END
    after = snapshot(db_session, context)
    freeze(monkeypatch, END + timedelta(hours=1))
    repeat = finalize(client, context)
    assert repeat.status_code == 409 and repeat.json() == {
        "detail": "No unresolved attendance to finalize"
    }
    assert snapshot(db_session, context) == after
    assert db_session.get(Activity, context[0]).cancelled_at is None
    balances = dict(db_session.execute(select(User.id, User.points_total)).all())
    assert balances == {
        user.id: COMPLETED_ACTIVITY_POINTS if index == 3 else 0
        for index, user in enumerate(context[1])
    }


@pytest.mark.parametrize(
    "offset,code",
    [
        (timedelta(microseconds=-1), 409),
        (timedelta(0), 200),
        (timedelta(microseconds=1), 200),
    ],
)
def test_finalization_exact_end_boundary(
    client, db_session, context, monkeypatch, offset, code
):
    before = snapshot(db_session, context)
    freeze(monkeypatch, END + offset)
    assert client.get(path(context), headers=context[2][0]).json()["permissions"][
        "can_finalize"
    ] is (code == 200)
    response = finalize(client, context)
    assert response.status_code == code
    if code == 409:
        assert response.json() == {
            "detail": "Activity can only be finalized after it ends"
        }
        assert snapshot(db_session, context) == before


@pytest.mark.parametrize(
    "credential", ["missing", "invalid", "expired", "refresh", "inactive", "unknown"]
)
def test_finalize_requires_valid_active_access_user(
    client, db_session, context, credential
):
    user_id = context[1][0].id
    if credential == "inactive":
        context[1][0].is_active = False
        db_session.commit()
    token = {
        "invalid": "bad",
        "expired": create_access_token(user_id, expires_delta=timedelta(seconds=-1)),
        "refresh": create_refresh_token(user_id),
        "unknown": create_access_token(uuid4()),
    }.get(credential, create_access_token(user_id))
    headers = {} if credential == "missing" else {"Authorization": f"Bearer {token}"}
    assert client.post(path(context) + "/finalize", headers=headers).status_code == 401


@pytest.mark.parametrize("user", [1, 5])
def test_only_organizer_can_finalize(client, context, monkeypatch, user):
    freeze(monkeypatch, END)
    response = finalize(client, context, user)
    assert response.status_code == 403
    assert response.json() == {"detail": "Only the organizer can manage this activity"}
    assert not client.get(path(context), headers=context[2][user]).json()[
        "permissions"
    ]["can_finalize"]


@pytest.mark.parametrize("activity_id,code", [(str(uuid4()), 404), ("invalid", 422)])
def test_finalize_unknown_or_invalid_activity(client, context, activity_id, code):
    assert (
        client.post(
            f"/api/v1/activities/{activity_id}/finalize", headers=context[2][0]
        ).status_code
        == code
    )


def test_cancelled_activity_cannot_finalize_and_preserves_all_evidence(
    client, db_session, context, monkeypatch
):
    assert (
        client.post(path(context) + "/cancel", headers=context[2][0]).status_code == 200
    )
    before = snapshot(db_session, context)
    freeze(monkeypatch, END)
    response = finalize(client, context)
    assert response.status_code == 409 and response.json() == {
        "detail": "Activity is cancelled"
    }
    assert snapshot(db_session, context) == before
    assert not client.get(path(context), headers=context[2][0]).json()["permissions"][
        "can_finalize"
    ]


@pytest.mark.parametrize("empty", [False, True])
def test_empty_or_left_only_activity_has_nothing_to_finalize(
    client, db_session, context, monkeypatch, empty
):
    db_session.execute(
        delete(ActivityParticipation).where(
            ActivityParticipation.activity_id == context[0],
            ActivityParticipation.user_id != context[1][4].id,
        )
    )
    if empty:
        db_session.execute(delete(ActivityParticipation))
    db_session.commit()
    freeze(monkeypatch, END)
    response = finalize(client, context)
    assert response.status_code == 409
    assert response.json() == {"detail": "No unresolved attendance to finalize"}
    assert not client.get(path(context), headers=context[2][0]).json()["permissions"][
        "can_finalize"
    ]


def test_existing_final_rows_are_never_rewritten_while_resolving_remaining_rows(
    client, db_session, context, monkeypatch
):
    current = rows(db_session, context)
    current[context[1][3].id].status = "COMPLETED"
    current[context[1][3].id].completed_at = END
    current[context[1][2].id].status = "NO_SHOW"
    current[context[1][2].id].no_show_at = END
    db_session.commit()
    before = snapshot(db_session, context)
    freeze(monkeypatch, END + timedelta(minutes=1))
    assert finalize(client, context).status_code == 200
    after = snapshot(db_session, context)
    for i in (2, 3, 4):
        assert after[context[1][i].id] == before[context[1][i].id]
    assert after[context[1][1].id][0] == "NO_SHOW"


def test_final_detail_and_history_are_private_and_left_stays_excluded(
    client, db_session, context, monkeypatch
):
    freeze(monkeypatch, END)
    assert finalize(client, context).status_code == 200
    for i, status in [
        (1, "NO_SHOW"),
        (2, "NO_SHOW"),
        (3, "COMPLETED"),
        (4, None),
        (5, None),
    ]:
        detail = client.get(path(context), headers=context[2][i]).json()
        member = detail["current_user_participation"]
        assert (member["status"] if member else None) == status
        assert_only_gallery_permissions(
            detail["permissions"],
            view=status == "COMPLETED",
            upload=status == "COMPLETED",
        )
        history = client.get(
            "/api/v1/users/me/activities",
            headers=context[2][i],
            params={"relation": "joined", "scope": "history"},
        ).json()
        assert len(history) == (1 if status else 0)
        all_times = client.get(
            "/api/v1/users/me/activities",
            headers=context[2][i],
            params={"relation": "joined"},
        ).json()
        assert all_times == history
        assert (
            client.get(
                "/api/v1/users/me/activities",
                headers=context[2][i],
                params={"relation": "joined", "scope": "upcoming"},
            ).json()
            == []
        )
        if member:
            assert history[0]["current_user_participation"] == member
            assert (member["completed_at"] is not None) is (status == "COMPLETED")
            assert (member["no_show_at"] is not None) is (status == "NO_SHOW")
    anonymous = client.get(path(context)).json()
    assert anonymous["current_user_participation"] is None
    assert "no_show_count" not in anonymous and "completed_count" not in anonymous
    assert "no_show_at" not in str(anonymous) and "completed_at" not in str(anonymous)
    assert anonymous["participant_count"] == 0 and anonymous["checked_in_count"] == 1
    assert client.get("/api/v1/activities").json() == []


@pytest.mark.parametrize("user", [1, 3])
@pytest.mark.parametrize("mutation", ["join", "leave", "confirm", "check-in"])
def test_final_outcomes_cannot_be_mutated_even_with_inconsistent_future_activity_dates(
    client, db_session, context, monkeypatch, user, mutation
):
    freeze(monkeypatch, END)
    assert finalize(client, context).status_code == 200
    before = snapshot(db_session, context)
    # Simulate imported final rows with future dates; terminal guards must still hold.
    activity = db_session.get(Activity, context[0])
    activity.start_at, activity.end_at = (
        END + timedelta(hours=1),
        END + timedelta(hours=2),
    )
    db_session.commit()
    method = client.delete if mutation == "leave" else client.post
    kwargs = (
        {"json": {"latitude": 52.4232, "longitude": 16.9461, "accuracy_m": 20}}
        if mutation == "check-in"
        else {}
    )
    response = method(
        path(context) + ("/join" if mutation == "leave" else f"/{mutation}"),
        headers=context[2][user],
        **kwargs,
    )
    assert response.status_code == 409 and response.json() == {
        "detail": "Attendance outcome is final"
    }
    assert snapshot(db_session, context) == before
    assert_only_gallery_permissions(
        client.get(path(context), headers=context[2][user]).json()["permissions"],
        view=user == 3,
        upload=user == 3,
    )
    assert (
        client.get(
            "/api/v1/users/me/activities",
            params={"relation": "joined", "scope": "upcoming"},
            headers=context[2][user],
        ).json()
        == []
    )


@pytest.mark.parametrize(
    "mutation", ["join", "leave", "confirm", "check-in", "patch", "cancel"]
)
def test_after_end_only_finalization_can_change_attendance(
    client, db_session, context, monkeypatch, mutation
):
    freeze(monkeypatch, END)
    before = snapshot(db_session, context)
    if mutation == "patch":
        response = client.patch(
            path(context), headers=context[2][0], json={"title": "Cannot reopen"}
        )
    elif mutation == "cancel":
        response = client.post(path(context) + "/cancel", headers=context[2][0])
    else:
        method = client.delete if mutation == "leave" else client.post
        kwargs = (
            {"json": {"latitude": 52.4232, "longitude": 16.9461, "accuracy_m": 20}}
            if mutation == "check-in"
            else {}
        )
        response = method(
            path(context) + ("/join" if mutation == "leave" else f"/{mutation}"),
            headers=context[2][1],
            **kwargs,
        )
    assert response.status_code == 409
    assert snapshot(db_session, context) == before


@pytest.mark.parametrize(
    "values",
    [
        {"status": "COMPLETED", "completed_at": END},
        {"status": "COMPLETED", "confirmed_at": START, "checked_in_at": START},
        {
            "status": "COMPLETED",
            "confirmed_at": START,
            "checked_in_at": START,
            "completed_at": END,
            "no_show_at": END,
        },
        {"status": "NO_SHOW"},
        {"status": "NO_SHOW", "no_show_at": END, "checked_in_at": START},
        {"status": "NO_SHOW", "no_show_at": END, "completed_at": END},
        {"status": "NO_SHOW", "no_show_at": END, "left_at": END},
        {"status": "JOINED", "completed_at": END},
        {"status": "JOINED", "no_show_at": END},
    ],
)
def test_final_timestamp_constraints_reject_impossible_combinations(
    db_session, context, values
):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            ActivityParticipation(
                activity_id=context[0], user_id=context[1][5].id, **values
            )
        )
        db_session.flush()


@pytest.mark.parametrize(
    "values",
    [
        {
            "status": "COMPLETED",
            "confirmed_at": START,
            "checked_in_at": START,
            "completed_at": END,
        },
        {"status": "NO_SHOW", "no_show_at": END},
        {"status": "NO_SHOW", "confirmed_at": START, "no_show_at": END},
    ],
)
def test_final_states_accept_realistic_nullable_confirmation_evidence(
    db_session, context, values
):
    db_session.add(
        ActivityParticipation(
            activity_id=context[0], user_id=context[1][5].id, **values
        )
    )
    db_session.flush()


@pytest.mark.parametrize("size", [1, 80])
@pytest.mark.parametrize("status", ["JOINED", "CHECKED_IN"])
def test_finalization_bulk_update_and_read_query_counts_are_constant(
    client, db_session, context, monkeypatch, size, status
):
    db_session.execute(delete(ActivityParticipation))
    db_session.get(Activity, context[0]).max_participants = None
    suffix = uuid4().hex
    extra = [
        User(
            email=f"bulk-{suffix}-{i}@example.com",
            display_name=f"Bulk{suffix}{i}",
            password_hash="unused",
        )
        for i in range(size)
    ]
    db_session.add_all(extra)
    db_session.flush()
    db_session.add_all(
        [
            ActivityParticipation(
                activity_id=context[0], user_id=user.id, status=status,
                confirmed_at=START if status == "CHECKED_IN" else None,
                checked_in_at=START if status == "CHECKED_IN" else None,
            )
            for user in extra
        ]
    )
    db_session.commit()
    freeze(monkeypatch, END)
    statements = []
    engine = db_session.get_bind()

    def record(_conn, _cursor, statement, _params, _context, _many):
        statements.append(statement.lstrip().upper())

    event.listen(engine, "before_cursor_execute", record)
    try:
        assert finalize(client, context).status_code == 200
        assert sum(s.startswith("SELECT") for s in statements) == 3
        assert (
            sum(s.startswith("UPDATE ACTIVITY_PARTICIPATIONS") for s in statements) == 1
        )
        assert sum(s.startswith("UPDATE USERS") for s in statements) == (
            1 if status == "CHECKED_IN" else 0
        )
        statements.clear()
        assert (
            client.get(
                "/api/v1/users/me/activities",
                headers=context[2][0],
                params={"relation": "organized"},
            ).status_code
            == 200
        )
        assert sum(s.startswith("SELECT") for s in statements) == 2
        statements.clear()
        client.get("/api/v1/activities")
        assert sum(s.startswith("SELECT") for s in statements) == 1
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_finalization_snapshot_failure_rolls_back_every_transition(
    client, db_session, context, monkeypatch
):
    before = snapshot(db_session, context)
    freeze(monkeypatch, END)

    def fail(*args, **kwargs):
        raise RuntimeError("Finalization snapshot failed")

    monkeypatch.setattr(management, "_snapshot", fail)
    with pytest.raises(RuntimeError, match="snapshot failed"):
        finalize(client, context)
    assert snapshot(db_session, context) == before


def test_finalize_openapi_has_auth_no_body_and_full_response(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/activities/{activity_id}/finalize"]["post"]
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert "requestBody" not in operation
    assert {"200", "401", "403", "404", "409", "422"} <= operation["responses"].keys()
    example = operation["responses"]["200"]["content"]["application/json"]["example"]
    assert example == ACTIVITY_FINALIZE_RESPONSE_EXAMPLE
    assert ActivityRead.model_validate(example).status == "ENDED"
    assert example["participant_count"] == 0 and example["checked_in_count"] == 1
    assert "COMPLETED" not in schema["components"]["schemas"]["ActivityStatus"]["enum"]
