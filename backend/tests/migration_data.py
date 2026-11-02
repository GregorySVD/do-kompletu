"""Seed historical user tables without using the current ORM column set."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import MetaData, Table


def insert_legacy_users(session, users):
    table = Table("users", MetaData(), autoload_with=session.connection())
    values = []
    for user in users:
        user.id = uuid4()
        user.points_total = 0
        user.is_active = True
        user.created_at = datetime.now(UTC)
        values.append(
            {column.name: getattr(user, column.name) for column in table.columns}
        )
    session.execute(table.insert(), values)
