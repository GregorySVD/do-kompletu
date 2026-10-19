from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from test_participation_lifecycle import freeze

from app.core.config import Settings, get_settings
from app.core.security import create_access_token, create_refresh_token
from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.schemas.activity import (
    ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE,
    ACTIVITY_CREATE_EXAMPLE,
    ActivityRead,
)
from app.schemas.activity_check_in import (
    ACTIVITY_CHECK_IN_REQUEST_EXAMPLE,
    ActivityCheckIn,
)
from app.services import participation_service as service

START = datetime(2030, 8, 8, 16, tzinfo=UTC)
NOW = START - timedelta(minutes=15)
COORDINATES = ACTIVITY_CHECK_IN_REQUEST_EXAMPLE
POSTGIS_CHECK = service._within_check_in_radius


@pytest.fixture
def context(client, db_session, monkeypatch):
    for name, value in {
        "ACTIVITY_CONFIRMATION_OPEN_MINUTES_BEFORE": "1440",
        "ACTIVITY_CONFIRMATION_DEADLINE_MINUTES_BEFORE": "0",
        "ACTIVITY_CHECK_IN_OPEN_MINUTES_BEFORE": "30",
        "ACTIVITY_CHECK_IN_CLOSE_MINUTES_AFTER": "60",
        "ACTIVITY_CHECK_IN_RADIUS_METERS": "150",
        "ACTIVITY_CHECK_IN_MAX_ACCURACY_METERS": "100",
    }.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    freeze(monkeypatch, NOW)
    # Only state/time/HTTP behavior is tested here, never geographic correctness.
    monkeypatch.setattr(service, "_within_check_in_radius", lambda *args: True)
    users = [
        User(
            email=f"checkin{i}@example.com",
            display_name=f"Checkin{i}",
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
        json={**ACTIVITY_CREATE_EXAMPLE, "min_participants": 2, "max_participants": 4},
    )
    assert response.status_code == 201
    yield UUID(response.json()["id"]), users, headers
    get_settings.cache_clear()


def path(context):
    return f"/api/v1/activities/{context[0]}"


def action(client, context, name, user=1, **kwargs):
    method = client.delete if name == "leave" else client.post
    suffix = "join" if name == "leave" else name
    if name == "check-in":
        kwargs.setdefault("json", COORDINATES)
    return method(path(context) + f"/{suffix}", headers=context[2][user], **kwargs)


def prepare(client, context, user=1):
    assert action(client, context, "join", user).status_code == 201
    assert action(client, context, "confirm", user).status_code == 200


def stored(db_session, context, user=1):
    return db_session.get(
        ActivityParticipation, (context[0], context[1][user].id), populate_existing=True
    )


def test_check_in_preserves_timestamps_and_disallows_duplicate_leave_confirm_join(
    client, db_session, context
):
    prepare(client, context)
    before = stored(db_session, context)
    joined, confirmed = before.joined_at, before.confirmed_at
    response = action(client, context, "check-in")
    assert response.status_code == 200
    body = response.json()
    row = stored(db_session, context)
    assert row.status == body["current_user_participation"]["status"] == "CHECKED_IN"
    assert (
        row.joined_at == joined
        and row.confirmed_at == confirmed
        and row.left_at is None
    )
    assert row.checked_in_at.replace(tzinfo=UTC) == NOW
    checked = row.checked_in_at
    assert body["participant_count"] == body["checked_in_count"] == 1
    assert body["available_slots"] == 3
    assert not any(body["permissions"].values())
    assert response.headers["cache-control"] == "private, no-store"
    for name, detail in [
        ("check-in", "Already checked in"),
        ("leave", "Checked-in participants cannot leave"),
        ("confirm", "Already checked in"),
        ("join", "Already joined this activity"),
    ]:
        response = action(client, context, name)
        assert response.status_code == 409 and response.json() == {"detail": detail}
    assert stored(db_session, context).checked_in_at == checked
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 1
    )


@pytest.mark.parametrize(
    "minutes,microseconds,code,detail",
    [
        (-30, -1, 409, "Check-in window has not opened"),
        (-30, 0, 200, None),
        (-15, 0, 200, None),
        (0, 0, 200, None),
        (60, -1, 200, None),
        (60, 0, 409, "Check-in window has closed"),
        (60, 1, 409, "Check-in window has closed"),
        (120, 0, 409, "Activity has ended"),
    ],
)
def test_exact_check_in_time_boundaries(
    client, db_session, context, monkeypatch, minutes, microseconds, code, detail
):
    prepare(client, context)
    freeze(monkeypatch, START + timedelta(minutes=minutes, microseconds=microseconds))
    body = client.get(path(context), headers=context[2][1]).json()
    assert body["permissions"]["can_check_in"] is (code == 200)
    response = action(client, context, "check-in")
    assert response.status_code == code
    if detail:
        assert response.json() == {"detail": detail}
        row = stored(db_session, context)
        assert row.status == "CONFIRMED" and row.checked_in_at is None


@pytest.mark.parametrize("offset", [timedelta(microseconds=-1), timedelta(0)])
def test_deadline_is_capped_by_activity_end(
    client, db_session, context, monkeypatch, offset
):
    activity = db_session.get(Activity, context[0])
    activity.end_at = START + timedelta(minutes=10)
    db_session.commit()
    prepare(client, context)
    freeze(monkeypatch, START + timedelta(minutes=10) + offset)
    detail = client.get(path(context), headers=context[2][1]).json()
    assert datetime.fromisoformat(detail["checkin_closes_at"]) == START + timedelta(
        minutes=10
    )
    assert action(client, context, "check-in").status_code == (
        200 if offset < timedelta(0) else 409
    )


@pytest.mark.parametrize(
    "identity", ["missing", "invalid", "expired", "refresh", "inactive", "unknown"]
)
def test_check_in_requires_active_access_identity(
    client, db_session, context, identity
):
    user_id = context[1][1].id
    if identity == "inactive":
        context[1][1].is_active = False
        db_session.commit()
    tokens = {
        "invalid": "invalid",
        "expired": create_access_token(user_id, expires_delta=timedelta(seconds=-1)),
        "refresh": create_refresh_token(user_id),
        "unknown": create_access_token(uuid4()),
    }
    headers = (
        {}
        if identity == "missing"
        else {
            "Authorization": f"Bearer {tokens.get(identity, create_access_token(user_id))}"
        }
    )
    assert (
        client.post(
            path(context) + "/check-in", headers=headers, json=COORDINATES
        ).status_code
        == 401
    )


@pytest.mark.parametrize("activity_id,code", [(str(uuid4()), 404), ("invalid", 422)])
def test_check_in_unknown_or_invalid_activity(client, context, activity_id, code):
    assert (
        client.post(
            f"/api/v1/activities/{activity_id}/check-in",
            headers=context[2][1],
            json=COORDINATES,
        ).status_code
        == code
    )


@pytest.mark.parametrize("state", ["organizer", "nonmember", "JOINED", "LEFT"])
def test_check_in_does_not_implicitly_confirm(client, context, state):
    if state in {"JOINED", "LEFT"}:
        action(client, context, "join")
    if state == "LEFT":
        action(client, context, "leave")
    response = action(client, context, "check-in", 0 if state == "organizer" else 1)
    assert response.status_code == 409
    expected = (
        "Organizer cannot check in to their own activity"
        if state == "organizer"
        else "Attendance must be confirmed before check-in"
        if state == "JOINED"
        else "Not participating in this activity"
    )
    assert response.json() == {"detail": expected}


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"latitude": 0, "accuracy_m": 20},
        {"longitude": 0, "accuracy_m": 20},
        {"latitude": 0, "longitude": 0},
        {**COORDINATES, "latitude": 91},
        {**COORDINATES, "latitude": -91},
        {**COORDINATES, "longitude": 181},
        {**COORDINATES, "longitude": -181},
        {**COORDINATES, "latitude": None},
        {**COORDINATES, "latitude": "invalid"},
        {**COORDINATES, "accuracy_m": 0},
        {**COORDINATES, "accuracy_m": -1},
        {**COORDINATES, "accuracy_m": None},
        {**COORDINATES, "accuracy_m": "invalid"},
        {**COORDINATES, "accuracy_m": "NaN"},
        {**COORDINATES, "accuracy_m": "Infinity"},
        {**COORDINATES, "accuracy_m": "-Infinity"},
        {**COORDINATES, "user_id": str(uuid4())},
    ],
)
def test_check_in_validates_request_body(client, context, payload):
    assert action(client, context, "check-in", json=payload).status_code == 422


def test_missing_check_in_body_is_validation_error(client, context):
    assert (
        client.post(path(context) + "/check-in", headers=context[2][1]).status_code
        == 422
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"latitude": -90, "longitude": -180, "accuracy_m": 20},
        {"latitude": 90, "longitude": 180, "accuracy_m": 20},
    ],
)
def test_coordinate_extremes_are_valid_schema_values(payload):
    assert ActivityCheckIn.model_validate(payload).model_dump() == payload


@pytest.mark.parametrize("accuracy", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_accuracy_is_rejected_by_schema(accuracy):
    with pytest.raises(ValidationError):
        ActivityCheckIn.model_validate({**COORDINATES, "accuracy_m": accuracy})


@pytest.mark.parametrize(
    "raw_accuracy,sanitized_input",
    [("NaN", "nan"), ("Infinity", "inf"), ("-Infinity", "-inf"), ("1e999", "inf")],
)
def test_raw_nonfinite_accuracy_returns_serializable_validation_error(
    client, context, raw_accuracy, sanitized_input
):
    response = client.post(
        path(context) + "/check-in",
        headers={**context[2][1], "Content-Type": "application/json"},
        content=(
            '{"latitude":52.4232,"longitude":16.9461,"accuracy_m":'
            + raw_accuracy
            + "}"
        ),
    )
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "finite_number"
    assert error["loc"] == ["body", "accuracy_m"]
    assert error["input"] == sanitized_input


def test_nonfinite_nested_extra_field_has_serializable_validation_error(client, context):
    response = client.post(
        path(context) + "/check-in",
        headers={**context[2][1], "Content-Type": "application/json"},
        content=(
            '{"latitude":52.4232,"longitude":16.9461,"accuracy_m":20,'
            '"extra":{"values":[NaN,Infinity,-Infinity]}}'
        ),
    )
    assert response.status_code == 422
    error = response.json()["detail"][0]
    assert error["type"] == "extra_forbidden"
    assert error["loc"] == ["body", "extra"]
    assert error["input"] == {"values": ["nan", "inf", "-inf"]}


@pytest.mark.parametrize(
    "maximum,accuracy,accepted",
    [
        (100, 20, True),
        (100, 100, True),
        (100, 100.0001, False),
        (37.5, 37.5, True),
        (37.5, 37.5001, False),
    ],
)
def test_configured_accuracy_limit_precedes_geographic_validation(
    client, db_session, context, monkeypatch, maximum, accuracy, accepted
):
    prepare(client, context)
    monkeypatch.setenv("ACTIVITY_CHECK_IN_MAX_ACCURACY_METERS", str(maximum))
    get_settings.cache_clear()
    geographic_calls = []

    def geographic_check(*args):
        geographic_calls.append(args)
        return True

    monkeypatch.setattr(service, "_within_check_in_radius", geographic_check)
    response = action(
        client, context, "check-in", json={**COORDINATES, "accuracy_m": accuracy}
    )
    assert response.status_code == (200 if accepted else 409)
    assert len(geographic_calls) == int(accepted)
    row = stored(db_session, context)
    assert row.status == ("CHECKED_IN" if accepted else "CONFIRMED")
    assert (row.checked_in_at is not None) is accepted
    if not accepted:
        assert response.json() == {
            "detail": "Location accuracy is insufficient for check-in"
        }


def test_location_rejection_preserves_state_even_when_can_check_in_is_true(
    client, db_session, context, monkeypatch
):
    prepare(client, context)
    assert client.get(path(context), headers=context[2][1]).json()["permissions"][
        "can_check_in"
    ]
    monkeypatch.setattr(service, "_within_check_in_radius", lambda *args: False)
    response = action(client, context, "check-in")
    assert response.status_code == 409 and response.json() == {
        "detail": "Outside check-in radius"
    }
    row = stored(db_session, context)
    assert row.status == "CONFIRMED" and row.checked_in_at is None


def test_sqlite_cannot_authorize_geographic_check_in(
    client, db_session, context, monkeypatch
):
    prepare(client, context)
    monkeypatch.setattr(service, "_within_check_in_radius", POSTGIS_CHECK)
    response = action(client, context, "check-in")
    assert response.status_code == 503 and response.json() == {
        "detail": "Check-in requires PostgreSQL/PostGIS"
    }
    assert stored(db_session, context).checked_in_at is None


@pytest.mark.parametrize("unlimited", [False, True])
def test_mixed_state_counts_my_activities_and_privacy(
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
    action(client, context, "join", 1)
    prepare(client, context, 2)
    prepare(client, context, 3)
    action(client, context, "check-in", 3)
    action(client, context, "join", 4)
    action(client, context, "leave", 4)
    for user, state in [
        (1, "JOINED"),
        (2, "CONFIRMED"),
        (3, "CHECKED_IN"),
        (4, None),
        (5, None),
    ]:
        body = client.get(path(context), headers=context[2][user]).json()
        assert body["participant_count"] == 3 and body["checked_in_count"] == 1
        assert body["available_slots"] == (None if unlimited else 1)
        membership = body["current_user_participation"]
        assert (membership["status"] if membership else None) == state
        if membership:
            assert (membership["checked_in_at"] is not None) is (state == "CHECKED_IN")
        items = client.get(
            "/api/v1/users/me/activities",
            headers=context[2][user],
            params={"relation": "joined"},
        ).json()
        assert len(items) == (1 if state else 0)
        if items:
            assert items[0]["current_user_participation"] == membership
    anonymous = client.get(path(context)).json()
    assert anonymous["current_user_participation"] is None and not any(
        anonymous["permissions"].values()
    )
    assert "checked_in_at" not in str(anonymous)
    assert client.get("/api/v1/activities").json()[0]["checked_in_count"] == 1
    assert (
        db_session.scalar(select(func.count()).select_from(ActivityParticipation)) == 4
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("latitude", 50),
        ("longitude", 19),
        ("location_name", "Different venue"),
        ("address", "Different address"),
        ("start_at", "2030-08-08T16:15:00Z"),
        ("end_at", "2030-08-08T19:00:00Z"),
    ],
)
def test_checked_in_activity_identity_cannot_change(client, context, field, value):
    prepare(client, context)
    if field not in {"start_at", "end_at"}:
        # CONFIRMED alone does not freeze venue identity.
        before = client.get(path(context)).json()
        assert (
            client.patch(
                path(context), headers=context[2][0], json={field: value}
            ).status_code
            == 200
        )
        assert (
            client.patch(
                path(context), headers=context[2][0], json={field: before[field]}
            ).status_code
            == 200
        )
    assert action(client, context, "check-in").status_code == 200
    original = client.get(path(context)).json()
    response = client.patch(path(context), headers=context[2][0], json={field: value})
    assert response.status_code == 409
    assert client.get(path(context)).json() == original
    same = client.patch(
        path(context),
        headers=context[2][0],
        json={field: original[field], "title": "Safe textual update"},
    )
    assert same.status_code == 200


def test_cancel_preserves_check_in_and_disables_actions(client, db_session, context):
    prepare(client, context)
    action(client, context, "check-in")
    before = stored(db_session, context).checked_in_at
    assert action(client, context, "cancel", 0).status_code == 200
    body = client.get(path(context), headers=context[2][1]).json()
    assert (
        body["status"] == "CANCELLED"
        and body["checked_in_count"] == body["participant_count"] == 1
    )
    assert body["current_user_participation"]["status"] == "CHECKED_IN"
    assert not any(body["permissions"].values())
    for name in ("join", "leave", "confirm", "check-in"):
        response = action(client, context, name)
        assert response.status_code == 409 and response.json() == {
            "detail": "Activity is cancelled"
        }
    assert stored(db_session, context).checked_in_at == before


def test_rejoin_clears_cycle_timestamps(client, db_session, context):
    prepare(client, context)
    action(client, context, "leave")
    assert action(client, context, "join").status_code == 201
    row = stored(db_session, context)
    assert (
        row.status == "JOINED"
        and row.confirmed_at is row.checked_in_at is row.left_at is None
    )


@pytest.mark.parametrize("cancelled", [False, True])
def test_checked_in_history_preserves_state(client, context, monkeypatch, cancelled):
    prepare(client, context)
    action(client, context, "check-in")
    if cancelled:
        action(client, context, "cancel", 0)
    freeze(monkeypatch, START + timedelta(hours=2))
    items = client.get(
        "/api/v1/users/me/activities",
        params={"relation": "joined", "scope": "history"},
        headers=context[2][1],
    ).json()
    assert (
        len(items) == 1
        and items[0]["current_user_participation"]["status"] == "CHECKED_IN"
    )
    assert not any(items[0]["permissions"].values())


@pytest.mark.parametrize(
    "setting,value",
    [
        ("activity_check_in_open_minutes_before", -1),
        ("activity_check_in_close_minutes_after", -1),
        ("activity_check_in_radius_meters", 0),
        ("activity_check_in_radius_meters", -1),
        ("activity_check_in_radius_meters", "invalid"),
        ("activity_check_in_max_accuracy_meters", 0),
        ("activity_check_in_max_accuracy_meters", -1),
        ("activity_check_in_max_accuracy_meters", "invalid"),
        ("activity_check_in_max_accuracy_meters", float("nan")),
        ("activity_check_in_max_accuracy_meters", float("inf")),
        ("activity_check_in_open_minutes_before", 525601),
    ],
)
def test_invalid_check_in_settings_rejected(setting, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="sqlite://", **{setting: value})


def test_settings_drive_both_window_metadata_and_mutation(client, context, monkeypatch):
    prepare(client, context)
    for name, value in [
        ("ACTIVITY_CHECK_IN_OPEN_MINUTES_BEFORE", "5"),
        ("ACTIVITY_CHECK_IN_CLOSE_MINUTES_AFTER", "0"),
        ("ACTIVITY_CHECK_IN_RADIUS_METERS", "42"),
    ]:
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    body = client.get(path(context), headers=context[2][1]).json()
    assert datetime.fromisoformat(body["checkin_opens_at"]) == START - timedelta(
        minutes=5
    )
    assert datetime.fromisoformat(body["checkin_closes_at"]) == START
    assert body["checkin_radius_m"] == 42
    assert action(client, context, "check-in").json() == {
        "detail": "Check-in window has not opened"
    }
    freeze(monkeypatch, START - timedelta(minutes=5))
    assert action(client, context, "check-in").status_code == 200


@pytest.mark.parametrize(
    "status,confirmed,checked,left",
    [
        ("CHECKED_IN", NOW, None, None),
        ("CHECKED_IN", None, NOW, None),
        ("CHECKED_IN", NOW, NOW, NOW),
        ("CONFIRMED", NOW, NOW, None),
        ("JOINED", None, NOW, None),
        ("LEFT", NOW, NOW, NOW),
    ],
)
def test_model_prevents_contradictory_check_in_timestamps(
    db_session, context, status, confirmed, checked, left
):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            ActivityParticipation(
                activity_id=context[0],
                user_id=context[1][1].id,
                status=status,
                confirmed_at=confirmed,
                checked_in_at=checked,
                left_at=left,
            )
        )
        db_session.flush()


def test_post_flush_failure_rolls_back_check_in(
    client, db_session, context, monkeypatch
):
    prepare(client, context)

    def fail(*args, **kwargs):
        raise RuntimeError("Snapshot failure")

    monkeypatch.setattr(service, "_snapshot", fail)
    with pytest.raises(RuntimeError, match="Snapshot failure"):
        action(client, context, "check-in")
    assert stored(db_session, context).status == "CONFIRMED"
    assert stored(db_session, context).checked_in_at is None


def test_check_in_openapi_examples_and_privacy_contract(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/activities/{activity_id}/check-in"]["post"]
    assert operation["security"] == [{"OAuth2PasswordBearer": []}]
    assert {"200", "401", "404", "409", "422", "503"} <= operation["responses"].keys()
    request = operation["requestBody"]["content"]["application/json"]
    assert request["examples"]["at_venue"]["value"] == COORDINATES
    example = operation["responses"]["200"]["content"]["application/json"]["example"]
    assert example == ACTIVITY_CHECK_IN_RESPONSE_EXAMPLE
    assert (
        ActivityRead.model_validate(example).current_user_participation.status
        == "CHECKED_IN"
    )
    fields = schema["components"]["schemas"]["ActivityCheckIn"]
    assert fields["additionalProperties"] is False
    assert set(fields["required"]) == {"latitude", "longitude", "accuracy_m"}
    assert fields["properties"]["latitude"]["minimum"] == -90
    assert fields["properties"]["longitude"]["maximum"] == 180
    assert fields["properties"]["accuracy_m"]["exclusiveMinimum"] == 0
    assert "accuracy_m" not in schema["components"]["schemas"]["ActivityRead"]["properties"]
