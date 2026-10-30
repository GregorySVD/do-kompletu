"""Isolated point rules and HTTP contracts; concurrency is tested on PostgreSQL."""

import pytest
import test_activity_finalization as attendance
from gallery_data import set_status
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from test_participation_lifecycle import freeze

from app.models.user import User
from app.services import activity_management_service as management
from app.services.participation_rules import COMPLETED_ACTIVITY_POINTS

context = attendance.context


def balances(session, context):
    return dict(
        session.execute(
            select(User.id, User.points_total).where(
                User.id.in_([u.id for u in context[1]])
            )
        ).all()
    )


@pytest.mark.parametrize("initial", [0, 30])
def test_completion_adds_points_preserves_balance_profile_and_retry(
    client, db_session, context, monkeypatch, initial
):
    context[1][3].points_total = initial
    db_session.commit()
    # Creating, joining, confirming and checking in have already happened.
    assert balances(db_session, context)[context[1][3].id] == initial
    freeze(monkeypatch, attendance.END)
    result = attendance.finalize(client, context)
    assert result.status_code == 200
    assert "points_total" not in result.json()
    expected = {
        u.id: initial + COMPLETED_ACTIVITY_POINTS if i == 3 else 0
        for i, u in enumerate(context[1])
    }
    assert balances(db_session, context) == expected
    states = attendance.rows(db_session, context)
    assert states[context[1][3].id].status == "COMPLETED"
    assert (
        states[context[1][1].id].status == states[context[1][2].id].status == "NO_SHOW"
    )
    assert states[context[1][4].id].status == "LEFT"
    for user in (0, 1, 2, 3, 4):
        profile = client.get("/api/v1/users/me", headers=context[2][user])
        assert profile.status_code == 200
        assert profile.json()["points_total"] == expected[context[1][user].id]
    before = attendance.snapshot(db_session, context)
    # A new request after the original commit models a retry after a lost response.
    repeat = attendance.finalize(client, context)
    assert repeat.status_code == 409
    assert repeat.json() == {"detail": "No unresolved attendance to finalize"}
    assert balances(db_session, context) == expected
    assert attendance.snapshot(db_session, context) == before


@pytest.mark.parametrize(
    "status",
    [
        "JOINED",
        "CONFIRMED",
        "LEFT",
        "WAITLISTED",
        "CONFIRMATION_EXPIRED",
        "WAITLIST_EXPIRED",
        "NO_SHOW",
        "COMPLETED",
    ],
)
def test_non_winning_states_are_not_rewarded_while_other_rows_finalize(
    client, db_session, context, monkeypatch, status
):
    set_status(db_session, context[0], context[1][5].id, status)
    context[1][5].points_total = 30
    db_session.commit()
    freeze(monkeypatch, attendance.END)
    assert attendance.finalize(client, context).status_code == 200
    current = attendance.rows(db_session, context)[context[1][5].id]
    assert current.status == (
        "NO_SHOW" if status in {"JOINED", "CONFIRMED"} else status
    )
    assert balances(db_session, context)[context[1][5].id] == 30
    assert balances(db_session, context)[context[1][3].id] == COMPLETED_ACTIVITY_POINTS


def test_two_checked_in_participants_receive_independent_awards(
    client, db_session, context, monkeypatch
):
    response = client.post(
        attendance.path(context) + "/check-in",
        headers=context[2][2],
        json={"latitude": 52.4232, "longitude": 16.9461, "accuracy_m": 20},
    )
    assert response.status_code == 200
    assert set(balances(db_session, context).values()) == {0}
    freeze(monkeypatch, attendance.END)
    assert attendance.finalize(client, context).status_code == 200
    assert balances(db_session, context) == {
        u.id: COMPLETED_ACTIVITY_POINTS if i in {2, 3} else 0
        for i, u in enumerate(context[1])
    }


def test_cancellation_keeps_checked_in_evidence_without_points(
    client, db_session, context, monkeypatch
):
    assert (
        client.post(
            attendance.path(context) + "/cancel", headers=context[2][0]
        ).status_code
        == 200
    )
    before = attendance.snapshot(db_session, context)
    freeze(monkeypatch, attendance.END)
    assert attendance.finalize(client, context).json() == {
        "detail": "Activity is cancelled"
    }
    assert attendance.snapshot(db_session, context) == before
    assert set(balances(db_session, context).values()) == {0}


def test_deactivated_checked_in_user_still_earns_attendance_points(
    client, db_session, context, monkeypatch
):
    context[1][3].is_active = False
    db_session.commit()
    assert client.get("/api/v1/users/me", headers=context[2][3]).status_code == 401
    freeze(monkeypatch, attendance.END)
    assert attendance.finalize(client, context).status_code == 200
    assert balances(db_session, context)[context[1][3].id] == COMPLETED_ACTIVITY_POINTS
    assert attendance.rows(db_session, context)[context[1][3].id].status == "COMPLETED"


@pytest.mark.parametrize("failure", ["points_update", "snapshot", "commit"])
def test_points_and_attendance_rollback_together_then_retry_once(
    client, db_session, context, monkeypatch, failure
):
    freeze(monkeypatch, attendance.END)
    before = attendance.snapshot(db_session, context)
    engine = db_session.get_bind()

    def fail_update(_conn, _cursor, statement, *_args):
        if statement.lstrip().upper().startswith("UPDATE USERS"):
            raise RuntimeError("Injected points failure")

    def fail_after_points(session, *_args):
        assert (
            session.scalar(select(User.points_total).where(User.id == context[1][3].id))
            == COMPLETED_ACTIVITY_POINTS
        )
        raise RuntimeError("Injected points failure")

    original_snapshot = management._snapshot
    if failure == "points_update":
        event.listen(engine, "before_cursor_execute", fail_update)
    elif failure == "snapshot":
        monkeypatch.setattr(management, "_snapshot", fail_after_points)
    else:
        event.listen(Session, "before_commit", fail_after_points)
    try:
        with pytest.raises(RuntimeError, match="Injected points failure"):
            attendance.finalize(client, context)
    finally:
        if failure == "points_update":
            event.remove(engine, "before_cursor_execute", fail_update)
        elif failure == "snapshot":
            monkeypatch.setattr(management, "_snapshot", original_snapshot)
        else:
            event.remove(Session, "before_commit", fail_after_points)
    assert attendance.snapshot(db_session, context) == before
    assert set(balances(db_session, context).values()) == {0}
    assert attendance.finalize(client, context).status_code == 200
    assert attendance.finalize(client, context).status_code == 409
    assert balances(db_session, context)[context[1][3].id] == COMPLETED_ACTIVITY_POINTS


def test_failed_eligibility_checks_never_award_points(
    client, db_session, context, monkeypatch
):
    assert attendance.finalize(client, context).status_code == 409  # Before end.
    freeze(monkeypatch, attendance.END)
    assert attendance.finalize(client, context, user=1).status_code == 403
    assert client.post(attendance.path(context) + "/finalize").status_code == 401
    assert set(balances(db_session, context).values()) == {0}


def test_client_cannot_set_registration_profile_or_finalization_points(
    client, db_session, context, monkeypatch
):
    forged = {"points": 999999, "points_delta": 999999, "points_total": 999999}
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": "points-attempt@example.com",
            "display_name": "PointsAttempt",
            "password": "StrongPassword123",
            **forged,
        },
    )
    assert registered.status_code == 201 and registered.json()["points_total"] == 0
    profile = client.patch("/api/v1/users/me", headers=context[2][3], json=forged)
    assert profile.status_code == 200 and profile.json()["points_total"] == 0
    freeze(monkeypatch, attendance.END)
    result = client.post(
        attendance.path(context) + "/finalize", headers=context[2][0], json=forged
    )
    assert (
        result.status_code == 200
    )  # This endpoint has no body contract; JSON is ignored.
    assert balances(db_session, context)[context[1][3].id] == COMPLETED_ACTIVITY_POINTS
    assert balances(db_session, context)[context[1][0].id] == 0
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/activities/{activity_id}/finalize"]["post"]
    assert "requestBody" not in operation
    assert "+10 points" in operation["description"]
    assert "locking" not in operation["description"].lower()
    for name in ("UserRegister", "UserUpdate", "ActivityCreate", "ActivityUpdate"):
        assert (
            not forged.keys()
            & schema["components"]["schemas"][name]["properties"].keys()
        )
