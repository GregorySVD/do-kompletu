from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.activity import Activity

TEAM_SPORT_CATEGORY_ID = "623c6216-f59e-4167-a238-bfda04d99488"
MUSIC_CATEGORY_ID = "0b3903dd-849f-478c-a7e4-225707ac41af"


def activity_payload(**overrides):
    payload = {
        "title": "Siatkówka na Orliku",
        "description": "Amatorski mecz siatkówki dla każdego chętnego.",
        "category_id": TEAM_SPORT_CATEGORY_ID,
        "start_at": "2030-08-08T16:00:00Z",
        "end_at": "2030-08-08T18:00:00Z",
        "location_name": "Orlik przy ul. Gdańskiej",
        "address": "ul. Gdańska 1, Poznań",
        "latitude": 52.4232,
        "longitude": 16.9461,
        "min_participants": 4,
        "has_participant_limit": True,
        "max_participants": 12,
        "price_type": "FREE",
        "price_amount": None,
    }
    payload.update(overrides)
    return payload


def register_and_login(client):
    registration = client.post(
        "/api/v1/auth/register",
        json={
            "email": "organizer@example.com",
            "password": "SecretPass123",
            "display_name": "Activity Organizer",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={
            "identifier": "organizer@example.com",
            "password": "SecretPass123",
        },
    )
    return registration.json(), login.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_activity(client, token: str, **overrides):
    return client.post(
        "/api/v1/activities",
        headers=auth_header(token),
        json=activity_payload(**overrides),
    )


def test_create_activity_requires_authentication(client):
    response = client.post("/api/v1/activities", json=activity_payload())

    assert response.status_code == 401


def test_authenticated_user_creates_activity_as_organizer(client, db_session):
    registered_user, token = register_and_login(client)

    response = create_activity(client, token)

    assert response.status_code == 201
    body = response.json()
    assert body["organizer"] == {
        "id": registered_user["id"],
        "display_name": "Activity Organizer",
        "avatar_url": None,
    }
    assert "password_hash" not in str(body)

    stored_activity = db_session.scalar(select(Activity))
    assert stored_activity is not None
    assert str(stored_activity.organizer_id) == registered_user["id"]


def test_create_rejects_client_supplied_organizer_id(client):
    _, token = register_and_login(client)
    payload = activity_payload()
    payload["organizer_id"] = str(uuid4())

    response = client.post(
        "/api/v1/activities",
        headers=auth_header(token),
        json=payload,
    )

    assert response.status_code == 422
    assert client.get("/api/v1/activities").json() == []


def test_create_rejects_invalid_time_range(client):
    _, token = register_and_login(client)

    response = create_activity(
        client,
        token,
        start_at="2030-08-08T18:00:00Z",
        end_at="2030-08-08T16:00:00Z",
    )

    assert response.status_code == 422


def test_create_rejects_naive_datetimes(client):
    _, token = register_and_login(client)

    response = create_activity(
        client,
        token,
        start_at="2030-08-08T16:00:00",
        end_at="2030-08-08T18:00:00",
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"min_participants": 1},
        {"min_participants": 6, "max_participants": 5},
        {"has_participant_limit": True, "max_participants": None},
        {"has_participant_limit": False, "max_participants": 12},
    ],
)
def test_create_rejects_invalid_participant_limits(client, overrides):
    _, token = register_and_login(client)

    response = create_activity(client, token, **overrides)

    assert response.status_code == 422


@pytest.mark.parametrize(
    "overrides",
    [
        {"price_type": "FREE", "price_amount": 10},
        {"price_type": "PAID", "price_amount": None},
        {"price_type": "PAID", "price_amount": -1},
        {"price_type": "PAID", "price_amount": 10.123},
    ],
)
def test_create_rejects_invalid_price_state(client, overrides):
    _, token = register_and_login(client)

    response = create_activity(client, token, **overrides)

    assert response.status_code == 422


def test_paid_activity_returns_numeric_amount_and_pln_currency(client):
    _, token = register_and_login(client)

    response = create_activity(
        client,
        token,
        price_type="PAID",
        price_amount=25.50,
    )

    assert response.status_code == 201
    assert response.json()["price_amount"] == 25.5
    assert response.json()["currency"] == "PLN"


def test_created_activity_appears_in_public_list(client):
    _, token = register_and_login(client)
    created = create_activity(client, token)

    response = client.get("/api/v1/activities")

    assert created.status_code == 201
    assert response.status_code == 200
    assert [activity["id"] for activity in response.json()] == [
        created.json()["id"]
    ]


def test_activity_list_matches_card_and_map_contract(client):
    _, token = register_and_login(client)
    create_activity(client, token)

    activity = client.get("/api/v1/activities").json()[0]

    assert activity["category"] == {
        "id": TEAM_SPORT_CATEGORY_ID,
        "name": "Sport zespołowy",
        "slug": "sport-zespolowy",
    }
    assert activity["latitude"] == pytest.approx(52.4232)
    assert activity["longitude"] == pytest.approx(16.9461)
    assert activity["distance_m"] is None
    assert activity["participant_count"] == 0
    assert activity["available_slots"] == 12
    assert activity["status"] == "PUBLISHED"


def test_get_activity_details_returns_organizer_without_password(client):
    _, token = register_and_login(client)
    created = create_activity(client, token).json()

    response = client.get(f"/api/v1/activities/{created['id']}")

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == activity_payload()["description"]
    assert body["organizer"]["display_name"] == "Activity Organizer"
    assert body["tags"] == []
    assert body["permissions"]["can_join"] is False
    assert body["confirmation_opens_at"] is None
    assert "password_hash" not in str(body)


def test_get_unknown_activity_returns_not_found(client):
    response = client.get(f"/api/v1/activities/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}


def test_list_supports_search_filters_and_pagination(client):
    _, token = register_and_login(client)
    first = create_activity(client, token).json()
    second_payload = deepcopy(activity_payload())
    second_payload.update(
        {
            "title": "Jam session",
            "category_id": MUSIC_CATEGORY_ID,
            "start_at": "2030-09-12T18:00:00Z",
            "end_at": "2030-09-12T21:00:00Z",
            "location_name": "Dom Kultury Stokrotka",
            "price_type": "PAID",
            "price_amount": 20,
        }
    )
    second = client.post(
        "/api/v1/activities",
        headers=auth_header(token),
        json=second_payload,
    ).json()

    search_results = client.get(
        "/api/v1/activities",
        params={"query": "Stokrotka"},
    ).json()
    category_results = client.get(
        "/api/v1/activities",
        params={"category_id": MUSIC_CATEGORY_ID},
    ).json()
    price_results = client.get(
        "/api/v1/activities",
        params={"price_type": "FREE"},
    ).json()
    paginated_results = client.get(
        "/api/v1/activities",
        params={"limit": 1, "offset": 1},
    ).json()

    assert [activity["id"] for activity in search_results] == [second["id"]]
    assert [activity["id"] for activity in category_results] == [second["id"]]
    assert [activity["id"] for activity in price_results] == [first["id"]]
    assert [activity["id"] for activity in paginated_results] == [second["id"]]
