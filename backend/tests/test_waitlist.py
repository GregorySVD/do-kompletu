from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import IntegrityError
from test_participation_lifecycle import freeze

from app.core.security import create_access_token
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityRead
from app.services.activity_service import get_activity_by_id

NOW = datetime(2030, 8, 8, 4, tzinfo=UTC)
START = NOW + timedelta(hours=12)


@pytest.fixture
def queue(client, db_session, monkeypatch):
    freeze(monkeypatch, NOW)
    users = [
        User(
            id=UUID(int=i + 1),
            email=f"queue{i}@example.com",
            display_name=f"Queue{i}",
            password_hash="unused",
        )
        for i in range(9)
    ]
    db_session.add_all(users)
    db_session.commit()
    headers = [
        {"Authorization": f"Bearer {create_access_token(user.id)}"} for user in users
    ]
    payload = {
        **ACTIVITY_CREATE_EXAMPLE,
        "min_participants": 2,
        "max_participants": 2,
        "start_at": START.isoformat(),
        "end_at": (START + timedelta(hours=2)).isoformat(),
    }
    response = client.post("/api/v1/activities", headers=headers[0], json=payload)
    assert response.status_code == 201
    return UUID(response.json()["id"]), users, headers, payload


def path(queue):
    return f"/api/v1/activities/{queue[0]}"


def action(client, queue, user, operation="join", **kwargs):
    method = client.delete if operation == "leave" else client.post
    return method(
        path(queue) + ("/join" if operation == "leave" else f"/{operation}"),
        headers=queue[2][user],
        **kwargs,
    )


def detail(client, queue, user):
    return client.get(path(queue), headers=queue[2][user]).json()


def row(db_session, queue, user):
    return db_session.get(
        ActivityParticipation, (queue[0], queue[1][user].id), populate_existing=True
    )


def fill(client, queue, waiters=(3, 4, 5)):
    for user in (1, 2, *waiters):
        response = action(client, queue, user)
        assert response.status_code == 201, response.text
        assert response.json()["current_user_participation"]["status"] == (
            "JOINED" if user in (1, 2) else "WAITLISTED"
        )


def test_full_join_real_counts_caller_positions_privacy_and_permissions(client, queue):
    fill(client, queue)
    for user, position in ((3, 1), (4, 2), (5, 3)):
        body = detail(client, queue, user)
        assert (
            body["participant_count"],
            body["waitlist_count"],
            body["available_slots"],
        ) == (2, 3, 0)
        participation = body["current_user_participation"]
        assert participation["status"] == "WAITLISTED"
        assert participation["waitlist_position"] == position
        assert datetime.fromisoformat(participation["waitlisted_at"]) == NOW
        assert all(
            participation[key] is None
            for key in (
                "joined_at",
                "confirmed_at",
                "checked_in_at",
                "completed_at",
                "no_show_at",
            )
        )
        assert body["permissions"]["can_leave"]
        assert not any(
            value for key, value in body["permissions"].items() if key != "can_leave"
        )
        assert action(client, queue, user).status_code == 409
    for user in (1, 2):
        assert (
            detail(client, queue, user)["current_user_participation"][
                "waitlist_position"
            ]
            is None
        )
    for user in (0, 6):
        assert detail(client, queue, user)["current_user_participation"] is None
    assert detail(client, queue, 6)["permissions"]["can_join"]
    anonymous = client.get(path(queue)).json()
    assert anonymous["current_user_participation"] is None
    assert not any(anonymous["permissions"].values())
    cards = client.get("/api/v1/activities").json()
    assert cards[0]["waitlist_count"] == 3 and cards[0]["participant_count"] == 2
    assert "current_user_participation" not in cards[0]


@pytest.mark.parametrize("confirmed", [False, True])
@pytest.mark.parametrize("timing", ["distinct", "equal", "microsecond"])
def test_active_leave_promotes_fifo_with_same_order_as_position(
    client, db_session, queue, monkeypatch, confirmed, timing
):
    fill(client, queue)
    if confirmed:
        assert action(client, queue, 1, "confirm").status_code == 200
    # Insert/request order is deliberately different from queue time order.
    times = (
        {3: NOW + timedelta(minutes=2), 4: NOW, 5: NOW + timedelta(minutes=1)}
        if timing == "distinct"
        else {
            i: NOW + timedelta(microseconds=(i - 3 if timing == "microsecond" else 0))
            for i in (3, 4, 5)
        }
    )
    for user, entered in times.items():
        row(db_session, queue, user).waitlisted_at = entered
    db_session.commit()
    expected = sorted(times, key=lambda user: (times[user], queue[1][user].id))
    for position, user in enumerate(expected, 1):
        assert (
            detail(client, queue, user)["current_user_participation"][
                "waitlist_position"
            ]
            == position
        )
    promoted_at = NOW + timedelta(minutes=5)
    freeze(monkeypatch, promoted_at)
    result = action(client, queue, 1, "leave")
    assert result.status_code == 200
    assert (
        result.json()["participant_count"] == 2 and result.json()["waitlist_count"] == 2
    )
    assert result.json()["current_user_participation"] is None
    promoted = detail(client, queue, expected[0])["current_user_participation"]
    assert promoted["status"] == "JOINED"
    assert promoted["waitlist_position"] is None
    assert datetime.fromisoformat(promoted["joined_at"]) == promoted_at
    assert datetime.fromisoformat(promoted["waitlisted_at"]) == times[expected[0]]
    assert all(
        promoted[key] is None
        for key in ("confirmed_at", "checked_in_at", "completed_at", "no_show_at")
    )
    assert detail(client, queue, expected[0])["permissions"]["can_confirm"]
    for position, user in enumerate(expected[1:], 1):
        assert (
            detail(client, queue, user)["current_user_participation"][
                "waitlist_position"
            ]
            == position
        )
    assert action(client, queue, expected[0], "confirm").status_code == 200


def test_waitlist_leave_preserves_never_joined_row_and_fresh_rejoin_moves_to_tail(
    client, db_session, queue, monkeypatch
):
    fill(client, queue)
    freeze(monkeypatch, NOW + timedelta(minutes=1))
    left = action(client, queue, 3, "leave")
    assert left.status_code == 200
    assert left.json()["current_user_participation"] is None
    assert (left.json()["participant_count"], left.json()["waitlist_count"]) == (2, 2)
    assert row(db_session, queue, 3).joined_at is None
    assert row(db_session, queue, 3).waitlisted_at.replace(tzinfo=UTC) == NOW
    assert row(db_session, queue, 3).left_at is not None
    assert (
        detail(client, queue, 4)["current_user_participation"]["waitlist_position"] == 1
    )
    assert action(client, queue, 3, "leave").status_code == 409
    freeze(monkeypatch, NOW + timedelta(minutes=2))
    rejoin = action(client, queue, 3).json()["current_user_participation"]
    assert rejoin["status"] == "WAITLISTED" and rejoin["waitlist_position"] == 3
    assert datetime.fromisoformat(rejoin["waitlisted_at"]) == NOW + timedelta(minutes=2)
    assert row(db_session, queue, 3).left_at is None
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 5
    )


@pytest.mark.parametrize("full", [False, True])
def test_left_rejoin_reuses_row_and_resets_active_cycle(
    client, db_session, queue, full
):
    action(client, queue, 1)
    action(client, queue, 1, "confirm")
    action(client, queue, 1, "leave")
    if full:
        action(client, queue, 2)
        action(client, queue, 3)
    result = action(client, queue, 1)
    assert result.status_code == 201
    membership = result.json()["current_user_participation"]
    assert membership["status"] == ("WAITLISTED" if full else "JOINED")
    assert (membership["joined_at"] is None) is full
    assert (membership["waitlisted_at"] is not None) is full
    assert row(db_session, queue, 1).confirmed_at is None
    assert row(db_session, queue, 1).left_at is None
    assert db_session.scalar(
        select(func.count()).select_from(ActivityParticipation)
    ) == (3 if full else 1)


def test_queue_departure_never_uses_unrelated_spare_capacity(client, db_session, queue):
    fill(client, queue)
    # Simulate out-of-band capacity; leaving a queue still must not invoke the
    # active-place release path. Ordinary PATCH would promote immediately.
    activity = db_session.get(Activity, queue[0])
    activity.max_participants = 3
    db_session.commit()
    result = action(client, queue, 3, "leave")
    assert result.status_code == 200
    assert result.json()["participant_count"] == 2
    assert result.json()["waitlist_count"] == 2
    assert (
        detail(client, queue, 4)["current_user_participation"]["status"] == "WAITLISTED"
    )


def test_waitlisted_departure_then_direct_rejoin_clears_queue_history(
    client, db_session, queue
):
    fill(client, queue)
    action(client, queue, 3, "leave")
    action(client, queue, 1, "leave")  # Promote user 4.
    action(client, queue, 2, "leave")  # Promote user 5.
    action(client, queue, 4, "leave")  # Now there is a free place.
    result = action(client, queue, 3)
    assert result.status_code == 201
    own = result.json()["current_user_participation"]
    assert own["status"] == "JOINED" and own["joined_at"] is not None
    assert own["waitlisted_at"] is None and own["waitlist_position"] is None
    assert row(db_session, queue, 3).left_at is None


@pytest.mark.parametrize(
    "offset", [timedelta(microseconds=-1), timedelta(0), timedelta(seconds=1)]
)
@pytest.mark.parametrize(
    "full,rejoin", [(False, False), (True, False), (False, True), (True, True)]
)
def test_join_cutoff_applies_to_direct_waitlist_and_rejoin(
    client, queue, monkeypatch, offset, full, rejoin
):
    if rejoin:
        action(client, queue, 3)
        action(client, queue, 3, "leave")
    if full:
        fill(client, queue, ())
    freeze(monkeypatch, START + offset)
    assert detail(client, queue, 3)["permissions"]["can_join"] is (
        offset < timedelta(0)
    )
    result = action(client, queue, 3)
    assert result.status_code == (201 if offset < timedelta(0) else 409)
    if result.status_code == 409:
        assert result.json() == {"detail": "Activity has started"}


@pytest.mark.parametrize("offset", [timedelta(0), timedelta(minutes=1)])
def test_leave_after_start_does_not_admit_waiter(client, queue, monkeypatch, offset):
    fill(client, queue)
    freeze(monkeypatch, START + offset)
    assert action(client, queue, 1, "leave").status_code == 200
    assert (
        detail(client, queue, 3)["current_user_participation"]["status"] == "WAITLISTED"
    )
    assert detail(client, queue, 3)["participant_count"] == 1
    assert action(client, queue, 3, "leave").status_code == 200


@pytest.mark.parametrize("maximum,promoted", [(3, 1), (4, 2), (8, 3), (None, 3)])
def test_capacity_increase_promotes_only_available_places(
    client, queue, maximum, promoted
):
    fill(client, queue)
    payload = {"max_participants": maximum}
    if maximum is None:
        payload["has_participant_limit"] = False
    result = client.patch(path(queue), headers=queue[2][0], json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["participant_count"] == 2 + promoted
    assert result.json()["waitlist_count"] == 3 - promoted
    for index, user in enumerate((3, 4, 5)):
        assert detail(client, queue, user)["current_user_participation"]["status"] == (
            "JOINED" if index < promoted else "WAITLISTED"
        )
    if maximum is None:
        assert (
            action(client, queue, 6).json()["current_user_participation"]["status"]
            == "JOINED"
        )


def test_capacity_reduction_cannot_evict_active_members(client, queue):
    fill(client, queue)
    client.patch(path(queue), headers=queue[2][0], json={"max_participants": 4})
    result = client.patch(
        path(queue), headers=queue[2][0], json={"max_participants": 2}
    )
    assert result.status_code == 409
    assert (
        detail(client, queue, 5)["current_user_participation"]["waitlist_position"] == 1
    )


@pytest.mark.parametrize("operation", ["confirm", "check-in"])
def test_waitlisted_cannot_confirm_or_check_in(client, queue, operation):
    fill(client, queue)
    kwargs = (
        {"json": {"latitude": 52.4, "longitude": 16.9}}
        if operation == "check-in"
        else {}
    )
    result = action(client, queue, 3, operation, **kwargs)
    assert result.status_code == 409
    assert result.json() == {"detail": "Not participating in this activity"}


def test_cancellation_preserves_waitlist_and_blocks_actions(client, db_session, queue):
    fill(client, queue)
    before = detail(client, queue, 3)["current_user_participation"]
    assert action(client, queue, 0, "cancel").status_code == 200
    for user in (1, 3, 6):
        assert action(client, queue, user).status_code == 409
        assert action(client, queue, user, "leave").status_code == 409
    assert (
        client.patch(
            path(queue), headers=queue[2][0], json={"max_participants": 8}
        ).status_code
        == 409
    )
    after = detail(client, queue, 3)
    assert after["current_user_participation"] == before
    assert after["waitlist_count"] == 3
    assert not any(after["permissions"].values())
    assert row(db_session, queue, 3).status == "WAITLISTED"


def test_finalization_preserves_waitlisted_history_without_attendance(
    client, queue, monkeypatch
):
    fill(client, queue)
    freeze(monkeypatch, START + timedelta(hours=2))
    assert action(client, queue, 0, "finalize").status_code == 200
    waiter = detail(client, queue, 3)
    assert waiter["participant_count"] == 0 and waiter["waitlist_count"] == 3
    assert waiter["current_user_participation"]["status"] == "WAITLISTED"
    assert not any(waiter["permissions"].values())
    assert action(client, queue, 3).status_code == 409
    assert action(client, queue, 3, "leave").status_code == 409
    for relation, expected in (("joined", []), ("waitlisted", [str(queue[0])])):
        result = client.get(
            "/api/v1/users/me/activities",
            headers=queue[2][3],
            params={"relation": relation, "scope": "history"},
        )
        assert [item["id"] for item in result.json()] == expected


def test_waitlist_only_end_has_no_attendance_to_finalize(client, queue, monkeypatch):
    fill(client, queue)
    freeze(monkeypatch, START)
    assert action(client, queue, 1, "leave").status_code == 200
    assert action(client, queue, 2, "leave").status_code == 200
    freeze(monkeypatch, START + timedelta(hours=2))
    result = action(client, queue, 0, "finalize")
    assert result.status_code == 409
    assert result.json() == {"detail": "No unresolved attendance to finalize"}
    assert detail(client, queue, 3)["waitlist_count"] == 3


@pytest.mark.parametrize("operation", ["leave", "edit"])
def test_promotion_rolls_back_together_with_triggering_mutation(
    client, db_session, queue, monkeypatch, operation
):
    import app.services.activity_management_service as management
    import app.services.participation_service as participation

    fill(client, queue)

    def fail(*args, **kwargs):
        raise RuntimeError("response snapshot failed")

    monkeypatch.setattr(
        participation if operation == "leave" else management, "_snapshot", fail
    )
    # For edit, let the pre-edit snapshot succeed, fail only after promotion.
    if operation == "edit":
        original = get_activity_by_id
        calls = []

        def edit_snapshot(session, activity_id, user_id, now):
            calls.append(1)
            if len(calls) > 1:
                fail()
            return original(session, activity_id, current_user_id=user_id, as_of=now)

        monkeypatch.setattr(management, "_snapshot", edit_snapshot)
    with pytest.raises(RuntimeError, match="response snapshot failed"):
        if operation == "leave":
            action(client, queue, 1, "leave")
        else:
            client.patch(path(queue), headers=queue[2][0], json={"max_participants": 4})
    assert row(db_session, queue, 1).status == "JOINED"
    assert row(db_session, queue, 3).status == "WAITLISTED"
    assert (
        db_session.get(Activity, queue[0], populate_existing=True).max_participants == 2
    )


@pytest.mark.parametrize(
    "values",
    [
        {"waitlisted_at": None},
        {"joined_at": NOW},
        {"confirmed_at": NOW},
        {"checked_in_at": NOW},
        {"completed_at": NOW},
        {"no_show_at": NOW},
        {"left_at": NOW},
        {"status": "JOINED"},
        {"status": "CONFIRMED", "confirmed_at": NOW},
        {"status": "CHECKED_IN", "confirmed_at": NOW, "checked_in_at": NOW},
        {
            "status": "COMPLETED",
            "confirmed_at": NOW,
            "checked_in_at": NOW,
            "completed_at": NOW,
        },
        {"status": "NO_SHOW", "no_show_at": NOW},
        {"status": "LEFT", "left_at": NOW, "waitlisted_at": None},
        {"status": "LEFT", "left_at": NOW, "confirmed_at": NOW},
    ],
)
def test_database_rejects_inconsistent_waitlist_and_never_joined_states(
    db_session, queue, values
):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            ActivityParticipation(
                activity_id=queue[0],
                user_id=queue[1][3].id,
                **{
                    "status": "WAITLISTED",
                    "waitlisted_at": NOW,
                    "joined_at": None,
                    **values,
                },
            )
        )
        db_session.flush()


def test_waitlisted_my_activities_pagination_scope_ownership_and_cancelled(
    client, queue, monkeypatch
):
    fill(client, queue)
    ids = [str(queue[0])]
    for day in (1, 2, 3):
        response = client.post(
            "/api/v1/activities",
            headers=queue[2][0],
            json={
                **queue[3],
                "start_at": (START + timedelta(days=day)).isoformat(),
                "end_at": (START + timedelta(days=day, hours=2)).isoformat(),
            },
        )
        activity_id = response.json()["id"]
        ids.append(activity_id)
        for user in (1, 2, 3):
            assert (
                client.post(
                    f"/api/v1/activities/{activity_id}/join", headers=queue[2][user]
                ).status_code
                == 201
            )
    action(client, queue, 0, "cancel")

    def page(user=3, **params):
        response = client.get(
            "/api/v1/users/me/activities",
            headers=queue[2][user],
            params={"relation": "waitlisted", **params},
        )
        assert response.status_code == 200
        return response.json()

    assert [item["id"] for item in page(scope="upcoming")] == ids
    assert page()[0]["status"] == "CANCELLED"
    assert [item["id"] for item in page(limit=2, offset=1)] == ids[1:3]
    assert page(offset=4) == []
    assert page(6) == [] and page(0) == [] and page(1) == []
    assert all(
        item["current_user_participation"]["waitlist_position"] == 1 for item in page()
    )
    freeze(monkeypatch, START + timedelta(minutes=1))
    assert [item["id"] for item in page(scope="upcoming")] == ids
    freeze(monkeypatch, START + timedelta(hours=2))
    assert [item["id"] for item in page(scope="history")] == ids[:1]
    assert [item["id"] for item in page(scope="upcoming")] == ids[1:]


@pytest.mark.parametrize("size", [1, 20])
def test_waitlist_list_detail_and_my_activities_have_constant_select_count(
    client, db_session, queue, size
):
    fill(client, queue)
    source = db_session.get(Activity, queue[0])
    for index in range(size - 1):
        activity = Activity(
            **{
                column.name: getattr(source, column.name)
                for column in Activity.__table__.columns
                if column.name not in {"id", "created_at", "updated_at"}
            }
        )
        db_session.add(activity)
        db_session.flush()
        db_session.add(
            ActivityParticipation(
                activity_id=activity.id,
                user_id=queue[1][3].id,
                status="WAITLISTED",
                joined_at=None,
                waitlisted_at=NOW,
            )
        )
    db_session.commit()
    statements = []

    def record(_conn, _cursor, statement, _params, _ctx, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", record)
    try:
        for url, params, headers, expected_count in (
            ("/api/v1/activities", {}, {}, 1),
            (path(queue), {}, queue[2][3], 2),
            (
                "/api/v1/users/me/activities",
                {"relation": "waitlisted", "limit": 100},
                queue[2][3],
                2,
            ),
        ):
            statements.clear()
            response = client.get(url, params=params, headers=headers)
            assert response.status_code == 200
            assert len(statements) == expected_count
            if params:
                assert len(response.json()) == size
                assert all(
                    item["current_user_participation"]["waitlist_position"] == 1
                    for item in response.json()
                )
    finally:
        event.remove(engine, "before_cursor_execute", record)


def test_openapi_waitlist_contract_and_examples(client):
    schema = client.get("/openapi.json").json()
    join = schema["paths"]["/api/v1/activities/{activity_id}/join"]["post"]
    media = join["responses"]["201"]["content"]["application/json"]
    assert set(media["examples"]) == {"joined", "waitlisted"}
    for example in media["examples"].values():
        ActivityRead.model_validate(example["value"])
    assert (
        media["examples"]["waitlisted"]["value"]["current_user_participation"][
            "joined_at"
        ]
        is None
    )
    conflicts = join["responses"]["409"]["content"]["application/json"][
        "examples"
    ].values()
    assert "Activity is full" not in {
        example["value"]["detail"] for example in conflicts
    }
    assert schema["components"]["schemas"]["ActivityRelation"]["enum"] == [
        "organized",
        "joined",
        "waitlisted",
    ]
