from datetime import UTC, datetime, timedelta

import pytest
from my_activities_data import AS_OF, freeze_activity_clock, seed_my_activities

from app.core.security import create_access_token
from app.schemas.activity import ActivityCategoryId
from app.services import activity_service

ENDPOINT = "/api/v1/activities"


@pytest.fixture
def discovery_data(db_session, monkeypatch):
    freeze_activity_clock(monkeypatch)
    data = seed_my_activities(db_session)
    data.activities["joined_a"].cancelled_at = AS_OF - timedelta(minutes=1)
    data.activities["own_old"].title = "Joined ended"
    db_session.commit()
    return data


def test_discovery_only_published_and_ongoing_at_strict_end_boundary(
    client, discovery_data
):
    response = client.get(ENDPOINT, params={"limit": 100})
    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == discovery_data.ids(
        "own_ongoing", "joined_ongoing", "just_after", "start_boundary",
        "joined_b", "not_joined", "unrelated", "own_upcoming", "joined_unlimited",
    )
    assert {item["status"] for item in items} == {"PUBLISHED", "ONGOING"}
    assert {item["id"] for item in items}.isdisjoint(discovery_data.ids(
        "boundary", "just_before", "history_old", "joined_a"
    ))


def test_discovery_applies_end_and_cancellation_filters_before_pagination(
    client, discovery_data
):
    # Historical rows have earlier starts, while joined_a is cancelled and tied
    # with joined_b; neither may consume a page slot, including after an offset.
    params = {
        "query": "joined",
        "category_id": ActivityCategoryId.TEAM_SPORT.value,
        "price_type": "FREE",
    }
    first = client.get(ENDPOINT, params={**params, "limit": 1, "offset": 0})
    second = client.get(ENDPOINT, params={**params, "limit": 1, "offset": 1})
    full = client.get(ENDPOINT, params={**params, "limit": 100})
    assert first.status_code == second.status_code == full.status_code == 200
    assert [item["id"] for item in first.json()] == discovery_data.ids("joined_ongoing")
    assert [item["id"] for item in second.json()] == discovery_data.ids("joined_b")
    assert [item["id"] for item in full.json()] == discovery_data.ids(
        "joined_ongoing", "joined_b", "not_joined", "joined_unlimited"
    )


@pytest.mark.parametrize(
    ("name", "status"), [("own_old", "ENDED"), ("joined_a", "CANCELLED")]
)
def test_discovery_omission_preserves_direct_detail(client, discovery_data, name, status):
    response = client.get(f"{ENDPOINT}/{discovery_data.activities[name].id}")
    assert response.status_code == 200
    assert response.json()["status"] == status


def test_discovery_omission_preserves_my_activities_history(client, discovery_data):
    headers = {
        "Authorization": f"Bearer {create_access_token(discovery_data.users[0].id)}"
    }
    response = client.get(
        "/api/v1/users/me/activities",
        headers=headers,
        params={"relation": "organized", "scope": "history"},
    )
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == discovery_data.ids(
        "own_recent", "own_old"
    )
    joined = client.get(
        "/api/v1/users/me/activities", headers=headers, params={"relation": "joined"}
    )
    assert joined.status_code == 200
    assert set(discovery_data.ids("history_old", "joined_a")) <= {
        item["id"] for item in joined.json()
    }


def test_discovery_uses_single_aware_cutoff_for_filter_and_response(
    client, discovery_data, monkeypatch
):
    calls = []

    class AdvancingDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            calls.append(tz)
            assert tz is UTC
            return AS_OF + timedelta(seconds=len(calls) - 1)

    monkeypatch.setattr(activity_service, "datetime", AdvancingDatetime)
    response = client.get(ENDPOINT, params={"limit": 100})
    assert response.status_code == 200
    assert calls == [UTC]
    boundary = next(
        item for item in response.json()
        if item["id"] == discovery_data.ids("just_after")[0]
    )
    assert boundary["status"] == "ONGOING"
