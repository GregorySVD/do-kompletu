import pytest
from sqlalchemy import event
from sqlalchemy.exc import (
    DisconnectionError,
    InterfaceError,
    OperationalError,
    ProgrammingError,
)
from sqlalchemy.exc import TimeoutError as DatabaseTimeoutError

from app.db.session import get_db
from app.main import app


def test_health_check(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_executes_only_select_one(client, session_factory):
    statements = []
    engine = session_factory.kw["bind"]

    def record(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        response = client.get("/ready")
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert statements == ["SELECT 1"]


@pytest.mark.parametrize(
    "failure",
    [
        OperationalError("SELECT 1", {}, RuntimeError("private-db-url/password")),
        InterfaceError("SELECT 1", {}, RuntimeError("private-db-url/password")),
        DisconnectionError("private-db-url/password"),
        DatabaseTimeoutError("private-db-url/password"),
    ],
)
def test_ready_connectivity_failure_is_nonsensitive_503(client, failure):
    class UnavailableSession:
        def execute(self, _statement):
            raise failure

    app.dependency_overrides[get_db] = lambda: UnavailableSession()
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database unavailable"}
    assert "private-db-url" not in response.text
    assert "SELECT" not in response.text


@pytest.mark.parametrize(
    "failure",
    [
        RuntimeError("unexpected application failure"),
        ProgrammingError("SELECT 1", {}, RuntimeError("unexpected SQL bug")),
    ],
)
def test_ready_does_not_disguise_programming_errors(client, failure):
    class BrokenSession:
        def execute(self, _statement):
            raise failure

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    with pytest.raises(type(failure)):
        client.get("/ready")


def test_health_does_not_resolve_or_use_database(client):
    def database_must_not_be_requested():
        raise AssertionError("Liveness must not request a database session")

    app.dependency_overrides[get_db] = database_must_not_be_requested
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_openapi(client):
    schema = client.get("/openapi.json").json()
    operation = schema["paths"]["/ready"]["get"]
    assert "SELECT 1" in operation["description"]
    assert operation["responses"]["503"]["content"]["application/json"]["example"] == {
        "detail": "Database unavailable"
    }
