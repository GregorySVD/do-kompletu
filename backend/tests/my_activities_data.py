from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models.activity import Activity
from app.models.activity_participation import ActivityParticipation
from app.models.user import User
from app.services.activity_service import _location_value

AS_OF = datetime(2030, 6, 1, 10, tzinfo=UTC)


@dataclass
class MyActivitiesData:
    users: list[User]
    activities: dict[str, Activity]

    def ids(self, *names: str) -> list[str]:
        return [str(self.activities[name].id) for name in names]


def seed_my_activities(session: Session) -> MyActivitiesData:
    suffix = uuid4().hex
    users = [
        User(
            email=f"my-activities-{suffix}-{index}@example.com",
            display_name=f"MyActivities{suffix}{index}",
            password_hash="unused-in-token-tests",
        )
        for index in range(4)
    ]
    session.add_all(users)
    session.flush()
    # Distinct across fixture invocations, ordered suffixes for equal-time tie tests.
    id_prefix = (uuid4().int >> 16) << 16
    activities = {}

    def activity(name, number, start, end, *, owner=1, maximum=4):
        item = Activity(
            id=UUID(int=id_prefix + number),
            organizer_id=users[owner].id,
            title=name.replace("_", " ").title(),
            description="An activity for My Activities contract tests.",
            category="sport-zespolowy",
            start_at=start,
            end_at=end,
            location_name="Poznan sports centre",
            address="ul. Piotrowo 2, Poznan",
            location=_location_value(session, 52.4005, 16.9516),
            min_participants=2,
            max_participants=maximum,
            price_type="FREE",
            price_amount=None,
        )
        session.add(item)
        activities[name] = item

    hour = timedelta(hours=1)
    day = timedelta(days=1)
    activity("own_ongoing", 1, AS_OF - hour, AS_OF + hour, owner=0)
    activity("own_upcoming", 2, AS_OF + 2 * hour, AS_OF + 3 * hour, owner=0)
    activity("own_old", 3, AS_OF - 3 * day, AS_OF - 2 * day, owner=0)
    activity("own_recent", 4, AS_OF - 2 * day, AS_OF - day, owner=0)
    activity("joined_ongoing", 10, AS_OF - hour, AS_OF + 2 * hour, maximum=2)
    activity("joined_a", 11, AS_OF + hour, AS_OF + 2 * hour)
    activity("joined_b", 12, AS_OF + hour, AS_OF + 2 * hour)
    activity("joined_unlimited", 13, AS_OF + 2 * hour, AS_OF + 3 * hour, maximum=None)
    activity("history_new_a", 14, AS_OF - 4 * hour, AS_OF - hour)
    activity("history_new_b", 15, AS_OF - 5 * hour, AS_OF - hour)
    activity("history_old", 16, AS_OF - 3 * day, AS_OF - 2 * day)
    activity("boundary", 17, AS_OF - hour, AS_OF)
    activity("just_before", 18, AS_OF - hour, AS_OF - timedelta(microseconds=1))
    activity("just_after", 19, AS_OF - hour, AS_OF + timedelta(microseconds=1))
    activity("start_boundary", 20, AS_OF, AS_OF + hour)
    activity("not_joined", 30, AS_OF + hour, AS_OF + 2 * hour)
    activity("unrelated", 31, AS_OF + hour, AS_OF + 2 * hour, owner=3)
    session.flush()
    for name, item in activities.items():
        if name not in {"not_joined", "unrelated"} and not name.startswith("own_"):
            session.add(
                ActivityParticipation(
                    activity_id=item.id,
                    user_id=users[0].id,
                    joined_at=AS_OF - 4 * day,
                )
            )
    for name in ("own_ongoing", "joined_ongoing", "not_joined"):
        session.add(
            ActivityParticipation(
                activity_id=activities[name].id,
                user_id=users[2].id,
                joined_at=AS_OF - 4 * day,
            )
        )
    session.commit()
    return MyActivitiesData(users, activities)


def freeze_activity_clock(monkeypatch):
    import app.services.activity_service as service

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return AS_OF if tz is not None else AS_OF.replace(tzinfo=None)

    monkeypatch.setattr(service, "datetime", FixedDatetime)
