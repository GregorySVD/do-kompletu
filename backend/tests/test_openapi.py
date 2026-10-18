from __future__ import annotations

from app.schemas.activity import (
    ACTIVITY_CATEGORIES,
    ACTIVITY_JOIN_RESPONSE_EXAMPLE,
    ACTIVITY_LEAVE_RESPONSE_EXAMPLE,
    ActivityCreate,
    ActivityRead,
    PriceType,
)


def test_categories_endpoint_returns_canonical_activity_categories(client):
    response = client.get("/api/v1/categories")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": category.id.value,
            "name": category.name,
            "slug": category.slug,
        }
        for category in ACTIVITY_CATEGORIES.values()
    ]


def test_openapi_oauth2_password_flow_uses_form_token_endpoint(client):
    schema = client.get("/openapi.json").json()

    password_flow = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"][
        "flows"
    ]["password"]

    assert password_flow["tokenUrl"] == "/api/v1/auth/token"


def test_openapi_json_login_uses_identifier_contract(client):
    schema = client.get("/openapi.json").json()
    login_schema = schema["components"]["schemas"]["UserLogin"]

    assert "identifier" in login_schema["properties"]
    assert "email" not in login_schema["properties"]
    assert login_schema["required"] == ["identifier", "password"]


def test_openapi_token_docs_explain_swagger_credentials(client):
    schema = client.get("/openapi.json").json()
    token_docs = schema["paths"]["/api/v1/auth/token"]["post"]["description"].lower()

    assert "email or display name" in token_docs
    assert "case-insensitive" in token_docs
    assert "case-sensitive" in token_docs
    assert "client_id" in token_docs
    assert "client_secret" in token_docs
    assert "blank" in token_docs


def test_openapi_activity_create_uses_valid_request_example(client):
    schema = client.get("/openapi.json").json()
    example = schema["paths"]["/api/v1/activities"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]["valid_free_activity"]["value"]

    validated_example = ActivityCreate.model_validate(example)

    assert validated_example.end_at > validated_example.start_at
    assert validated_example.price_type.value == "FREE"
    assert validated_example.price_amount is None


def test_openapi_activity_create_has_three_valid_selectable_examples(client):
    schema = client.get("/openapi.json").json()
    examples = schema["paths"]["/api/v1/activities"]["post"]["requestBody"]["content"][
        "application/json"
    ]["examples"]

    assert set(examples) == {
        "valid_free_activity",
        "free_unbounded",
        "paid_bounded",
    }

    validated = [
        ActivityCreate.model_validate(example["value"]) for example in examples.values()
    ]
    assert all(item.end_at > item.start_at for item in validated)
    assert any(
        item.price_type == PriceType.FREE and item.has_participant_limit
        for item in validated
    )
    assert any(
        item.price_type == PriceType.FREE and not item.has_participant_limit
        for item in validated
    )
    assert any(
        item.price_type == PriceType.PAID and item.has_participant_limit
        for item in validated
    )


def test_openapi_activity_create_docs_list_every_canonical_category(client):
    schema = client.get("/openapi.json").json()
    create_docs = schema["paths"]["/api/v1/activities"]["post"]["description"]

    for category in ACTIVITY_CATEGORIES.values():
        assert category.id.value in create_docs
        assert category.name in create_docs
        assert category.slug in create_docs


def test_openapi_activity_create_docs_explain_price_and_participant_rules(client):
    schema = client.get("/openapi.json").json()
    create_docs = schema["paths"]["/api/v1/activities"]["post"]["description"].lower()

    assert "## participants" in create_docs
    assert "has_participant_limit" in create_docs
    assert "max_participants" in create_docs
    assert "## price" in create_docs
    assert "free" in create_docs
    assert "paid" in create_docs
    assert "price_amount" in create_docs


def test_openapi_categories_endpoint_is_documented_as_activity_reference_data(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/categories"]["get"]
    description = operation["description"]

    assert operation["summary"] == "List activity categories"
    assert "ActivityCreate.category_id" in description
    assert "id" in description
    assert "name" in description
    assert "slug" in description


def test_openapi_has_documented_tags_and_endpoint_summaries(client):
    schema = client.get("/openapi.json").json()
    tags = {tag["name"]: tag["description"] for tag in schema["tags"]}

    assert set(tags) == {
        "Authentication",
        "Users",
        "Activities",
        "Reference Data",
        "Health",
    }
    assert schema["paths"]["/api/v1/auth/register"]["post"]["summary"]
    assert schema["paths"]["/api/v1/auth/login"]["post"]["summary"]
    assert schema["paths"]["/api/v1/auth/token"]["post"]["summary"]
    assert schema["paths"]["/api/v1/auth/refresh"]["post"]["summary"]
    assert schema["paths"]["/api/v1/users/me"]["get"]["summary"]
    assert schema["paths"]["/api/v1/categories"]["get"]["summary"]
    assert schema["paths"]["/api/v1/activities"]["post"]["summary"]
    assert schema["paths"]["/api/v1/activities"]["get"]["summary"]
    assert schema["paths"]["/api/v1/activities/{activity_id}"]["get"]["summary"]


def test_openapi_membership_endpoints_document_auth_conflicts_and_valid_examples(
    client,
):
    schema = client.get("/openapi.json").json()
    path = schema["paths"]["/api/v1/activities/{activity_id}/join"]
    for method, success in [("post", "201"), ("delete", "200")]:
        operation = path[method]
        assert operation["summary"]
        assert operation["security"] == [{"OAuth2PasswordBearer": []}]
        assert {success, "401", "404", "409", "422"} <= operation["responses"].keys()
        assert "requestBody" not in operation
        example = operation["responses"][success]["content"]["application/json"][
            "example"
        ]
        activity = ActivityRead.model_validate(example)
        assert example == (
            ACTIVITY_JOIN_RESPONSE_EXAMPLE
            if method == "post"
            else ACTIVITY_LEAVE_RESPONSE_EXAMPLE
        )
        assert activity.participant_count == (1 if method == "post" else 0)
        assert activity.permissions.can_leave is (method == "post")
        assert activity.permissions.can_join is (method == "delete")
        conflicts = operation["responses"]["409"]["content"]["application/json"][
            "examples"
        ]
        details = {example["value"]["detail"] for example in conflicts.values()}
        assert "Activity has ended" in details
        assert "Organizer cannot join or leave their own activity" in details


def test_openapi_detail_documents_optional_auth_and_membership_shape(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/api/v1/activities/{activity_id}"]["get"]
    assert "optional" in operation["description"].lower()
    assert operation["security"] == [{"OAuth2PasswordBearer": []}, {}]
    assert "401" in operation["responses"]
    membership = schema["components"]["schemas"]["ActivityParticipationRead"]
    assert membership["properties"]["status"]["const"] == "JOINED"
    assert membership["properties"]["joined_at"]["format"] == "date-time"
