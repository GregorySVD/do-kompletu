from __future__ import annotations

import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models.user import User
from app.schemas.activity import ActivityCreate
from app.services.activity_service import activity_to_read, create_activity

POSTGRES_TEST_DATABASE_URL = os.getenv("POSTGRES_TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    POSTGRES_TEST_DATABASE_URL is None,
    reason="POSTGRES_TEST_DATABASE_URL is not configured",
)


def test_postgres_geography_round_trip():
    engine = create_engine(POSTGRES_TEST_DATABASE_URL)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            session = Session(bind=connection, join_transaction_mode="create_savepoint")
            unique_suffix = uuid4().hex

            try:
                organizer = User(
                    email=f"activity-{unique_suffix}@example.com",
                    password_hash="not-a-real-password-hash",
                    display_name=f"Activity{unique_suffix}",
                )
                session.add(organizer)
                session.commit()

                result = create_activity(
                    session,
                    ActivityCreate.model_validate(
                        {
                            "title": "PostGIS round trip",
                            "description": "PostgreSQL geography integration test.",
                            "category_id": "1e3de603-e9fa-432c-8634-6e1298e53bf3",
                            "start_at": "2030-08-08T16:00:00Z",
                            "end_at": "2030-08-08T18:00:00Z",
                            "location_name": "Politechnika Poznańska",
                            "address": "ul. Piotrowo 2, Poznań",
                            "latitude": 52.4005,
                            "longitude": 16.9516,
                            "min_participants": 2,
                            "has_participant_limit": False,
                            "max_participants": None,
                            "price_type": "FREE",
                            "price_amount": None,
                        }
                    ),
                    organizer,
                )
                activity = activity_to_read(result)

                assert activity.latitude == pytest.approx(52.4005)
                assert activity.longitude == pytest.approx(16.9516)
            finally:
                session.close()
                transaction.rollback()
    finally:
        engine.dispose()
