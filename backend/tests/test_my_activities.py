from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
from my_activities_data import AS_OF, freeze_activity_clock, seed_my_activities
from sqlalchemy import event

from app.core.security import create_access_token, create_refresh_token
from app.models.activity_participation import ActivityParticipation
from app.schemas.activity import ACTIVITY_CREATE_EXAMPLE, ActivityRead

ENDPOINT = "/api/v1/users/me/activities"


@pytest.fixture
def data(db_session, monkeypatch):
    freeze_activity_clock(monkeypatch)
    return seed_my_activities(db_session)


def headers(data, user=0):
    return {"Authorization": f"Bearer {create_access_token(data.users[user].id)}"}


def page(client, data, **params):
    response = client.get(ENDPOINT, headers=headers(data), params=params)
    assert response.status_code == 200, response.text
    return response.json()


def ids(items):
    return [item["id"] for item in items]


def test_my_activities_requires_authentication(client):
    response = client.get(ENDPOINT, params={"relation": "organized"})
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "credential", ["invalid", "expired", "refresh", "unknown-user", "inactive", "basic"]
)
def test_my_activities_rejects_invalid_credentials(
    client, db_session, data, credential
):
    user = data.users[0]
    if credential == "expired":
        token = create_access_token(user.id, expires_delta=timedelta(seconds=-1))
    elif credential == "refresh":
        token = create_refresh_token(user.id)
    elif credential == "unknown-user":
        token = create_access_token(uuid4())
    elif credential == "inactive":
        user.is_active = False
        db_session.commit()
        token = create_access_token(user.id)
    else:
        token = "invalid-token"
    authorization = "Basic dXNlcjpwYXNz" if credential == "basic" else f"Bearer {token}"
    response = client.get(
        ENDPOINT,
        params={"relation": "joined"},
        headers={"Authorization": authorization},
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_organized_list_is_scoped_to_caller_and_includes_all_times(client, data):
    items = page(client, data, relation="organized")
    assert ids(items) == data.ids(
        "own_ongoing", "own_upcoming", "own_recent", "own_old"
    )
    for item in items:
        assert item["organizer"]["id"] == str(data.users[0].id)
        assert item["current_user_participation"] is None
        assert item["permissions"]["can_edit"] is (item["status"] == "PUBLISHED")
        assert item["permissions"]["can_cancel"] is (item["status"] != "ENDED")
        assert not any(
            value
            for key, value in item["permissions"].items()
            if key not in {"can_edit", "can_cancel"}
        )
        assert "email" not in item["organizer"]
        assert "password_hash" not in str(item)
    assert (
        items[0]["participant_count"] == 1
    )  # Another user's membership, not the organizer.
    assert items[0]["available_slots"] == 3
    assert items[1]["participant_count"] == 0
    assert items[1]["available_slots"] == 4


def test_joined_list_requires_own_membership_and_excludes_organized_activities(
    client, data
):
    items = page(client, data, relation="joined")
    expected = set(
        data.ids(
            *[
                name
                for name in data.activities
                if not name.startswith("own_")
                and name not in {"not_joined", "unrelated"}
            ]
        )
    )
    assert set(ids(items)) == expected
    assert len(items) == len(expected)
    for item in items:
        assert item["organizer"]["id"] != str(data.users[0].id)
        assert item["current_user_participation"] == {
            "status": "JOINED",
            "joined_at": (AS_OF - timedelta(days=4)).isoformat().replace("+00:00", "Z"),
        }
        assert item["permissions"]["can_join"] is False
        assert item["permissions"]["can_leave"] is (item["status"] != "ENDED")
        assert item["checked_in_count"] == item["waitlist_count"] == 0


@pytest.mark.parametrize("relation", ["organized", "joined"])
def test_upcoming_and_history_form_a_disjoint_complete_partition(
    client, data, relation
):
    upcoming = page(client, data, relation=relation, scope="upcoming")
    history = page(client, data, relation=relation, scope="history")
    all_items = page(client, data, relation=relation)
    assert set(ids(upcoming)).isdisjoint(ids(history))
    assert ids(all_items) == ids(upcoming) + ids(history)
    assert all(datetime.fromisoformat(item["end_at"]) > AS_OF for item in upcoming)
    assert all(item["status"] in {"PUBLISHED", "ONGOING"} for item in upcoming)
    assert all(datetime.fromisoformat(item["end_at"]) <= AS_OF for item in history)
    assert all(item["status"] == "ENDED" for item in history)


def test_boundaries_and_deterministic_sorting(client, data):
    upcoming = page(client, data, relation="joined", scope="upcoming")
    history = page(client, data, relation="joined", scope="history")
    assert ids(upcoming) == data.ids(
        "joined_ongoing",
        "just_after",
        "start_boundary",
        "joined_a",
        "joined_b",
        "joined_unlimited",
    )
    assert ids(history) == data.ids(
        "boundary", "just_before", "history_new_a", "history_new_b", "history_old"
    )
    ongoing = next(
        item for item in upcoming if item["id"] == data.ids("start_boundary")[0]
    )
    assert ongoing["status"] == "ONGOING"
    for scope, expected in [("upcoming", upcoming), ("history", history)]:
        assert page(client, data, relation="joined", scope=scope) == expected


def test_filter_and_status_share_one_cutoff_even_if_serialization_crosses_end(
    client, data, monkeypatch
):
    import app.services.activity_service as service

    calls = []

    class AdvancingDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(True)
            return AS_OF if len(calls) == 1 else AS_OF + timedelta(days=10)

    monkeypatch.setattr(service, "datetime", AdvancingDatetime)
    items = page(client, data, relation="joined", scope="upcoming")
    almost_ended = next(
        item for item in items if item["id"] == data.ids("just_after")[0]
    )
    assert almost_ended["status"] == "ONGOING"
    assert almost_ended["permissions"]["can_leave"] is True
    assert len(calls) == 1


@pytest.mark.parametrize("scope", [None, "upcoming", "history"])
@pytest.mark.parametrize("relation", ["organized", "joined"])
def test_limit_offset_apply_after_relation_and_scope(client, data, relation, scope):
    params = {"relation": relation}
    if scope is not None:
        params["scope"] = scope
    all_items = page(client, data, **params)
    assert page(client, data, **params, limit=1) == all_items[:1]
    assert page(client, data, **params, limit=2, offset=1) == all_items[1:3]
    assert page(client, data, **params, offset=100) == []


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"relation": "all"},
        {"relation": "participant"},
        {"scope": "upcoming"},
        {"relation": "joined", "scope": "all"},
        {"relation": "joined", "scope": "ongoing"},
        {"relation": "joined", "scope": ""},
        {"relation": "joined", "scope": "null"},
        {"relation": "joined", "limit": 0},
        {"relation": "joined", "limit": -1},
        {"relation": "joined", "limit": 101},
        {"relation": "joined", "limit": "abc"},
        {"relation": "joined", "limit": "1.5"},
        {"relation": "joined", "offset": -1},
        {"relation": "joined", "offset": "abc"},
        {"relation": "joined", "offset": "1.5"},
        {"relation": "joined", "user_id": str(uuid4())},
        {"relation": "joined", "typo": "upcoming"},
    ],
)
def test_invalid_query_parameters_return_validation_errors(client, data, params):
    response = client.get(ENDPOINT, params=params, headers=headers(data))
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], list)


def test_full_unlimited_and_real_counts(client, data):
    items = {item["id"]: item for item in page(client, data, relation="joined")}
    full = items[data.ids("joined_ongoing")[0]]
    assert full["participant_count"] == 2
    assert full["available_slots"] == 0
    assert full["permissions"]["can_leave"] is True
    unlimited = items[data.ids("joined_unlimited")[0]]
    assert unlimited["participant_count"] == 1
    assert unlimited["max_participants"] is unlimited["available_slots"] is None


@pytest.mark.parametrize("relation", ["organized", "joined"])
def test_empty_user_results_and_no_other_users_private_state(client, data, relation):
    response = client.get(
        ENDPOINT, params={"relation": relation}, headers=headers(data, 2)
    )
    assert response.status_code == 200
    items = response.json()
    if relation == "organized":
        assert items == []
    else:
        assert set(ids(items)) == set(
            data.ids("own_ongoing", "joined_ongoing", "not_joined")
        )
    empty = client.get(
        ENDPOINT, params={"relation": "joined"}, headers=headers(data, 3)
    )
    assert empty.json() == []


def test_join_leave_immediately_updates_my_lists(client, data):
    path = f"/api/v1/activities/{data.activities['not_joined'].id}/join"
    assert client.post(path, headers=headers(data)).status_code == 201
    assert data.ids("not_joined")[0] in ids(page(client, data, relation="joined"))
    assert client.delete(path, headers=headers(data)).status_code == 200
    assert data.ids("not_joined")[0] not in ids(page(client, data, relation="joined"))


def test_offset_datetimes_are_normalized_before_scope_comparison(client, data):
    response = client.post(
        "/api/v1/activities",
        headers=headers(data),
        json={
            **ACTIVITY_CREATE_EXAMPLE,
            "start_at": "2030-06-01T08:00:00+02:00",
            "end_at": "2030-06-01T12:00:00+02:00",
        },
    )
    assert response.status_code == 201
    item_id = response.json()["id"]
    history = page(client, data, relation="organized", scope="history")
    assert item_id in ids(history)
    assert item_id not in ids(
        page(client, data, relation="organized", scope="upcoming")
    )
    item = next(item for item in history if item["id"] == item_id)
    assert item["end_at"] == AS_OF.isoformat().replace("+00:00", "Z")
    assert item["status"] == "ENDED"


def test_personal_pages_are_private_arrays_compatible_with_detail_schema(client, data):
    response = client.get(
        ENDPOINT, params={"relation": "joined"}, headers=headers(data)
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["vary"] == "Authorization"
    assert isinstance(response.json(), list)
    for item in response.json():
        ActivityRead.model_validate(item)


def test_default_limit_is_twenty_and_maximum_is_one_hundred(client, db_session, data):
    original = data.activities["joined_a"]
    for index in range(25):
        # Use a fresh ORM instance rather than copying SQLAlchemy instance state.
        fields = {
            column.name: getattr(original, column.name)
            for column in original.__table__.columns
        }
        fields["id"] = uuid4()
        fields["title"] = f"Additional activity {index}"
        activity = type(original)(**fields)
        db_session.add(activity)
        db_session.flush()
        db_session.add(
            ActivityParticipation(activity_id=activity.id, user_id=data.users[0].id)
        )
    db_session.commit()
    assert len(page(client, data, relation="joined")) == 20
    assert len(page(client, data, relation="joined", limit=100)) == 36


@pytest.mark.parametrize("relation", ["organized", "joined"])
def test_listing_query_count_is_constant_for_one_and_many_items(
    client, db_session, data, relation
):
    engine = db_session.get_bind()
    statements = []

    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        page(client, data, relation=relation, limit=1)
        assert (
            len(statements) == 2
        )  # One authentication lookup, one activity projection.
        statements.clear()
        items = page(client, data, relation=relation, limit=100)
        assert len(items) > 1
        assert len(statements) == 2
        statements.clear()
        assert (
            client.get("/api/v1/activities", params={"limit": 100}).status_code == 200
        )
        assert len(statements) == 1
    finally:
        event.remove(engine, "before_cursor_execute", record)
