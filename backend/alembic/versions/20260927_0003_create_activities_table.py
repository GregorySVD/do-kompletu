from __future__ import annotations

import sqlalchemy as sa
from geoalchemy2 import Geography

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260927_0003"
down_revision = "20260927_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organizer_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("location_name", sa.String(length=120), nullable=False),
        sa.Column("address", sa.String(length=300), nullable=False),
        sa.Column(
            "location",
            Geography(geometry_type="POINT", srid=4326, spatial_index=False),
            nullable=False,
        ),
        sa.Column("min_participants", sa.Integer(), nullable=False),
        sa.Column("max_participants", sa.Integer(), nullable=True),
        sa.Column("price_type", sa.String(length=10), nullable=False),
        sa.Column("price_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ("
            "'sport-zespolowy', 'gry-planszowe', 'rpg', 'gaming', "
            "'wspolna-nauka', 'technologia', 'muzyka', 'kreatywne'"
            ")",
            name="ck_activities_category",
        ),
        sa.CheckConstraint(
            "min_participants BETWEEN 2 AND 100 "
            "AND (max_participants IS NULL "
            "OR max_participants BETWEEN min_participants AND 100)",
            name="ck_activities_participant_limits",
        ),
        sa.CheckConstraint(
            "(price_type = 'FREE' AND price_amount IS NULL) "
            "OR (price_type = 'PAID' AND price_amount > 0)",
            name="ck_activities_price",
        ),
        sa.CheckConstraint(
            "price_type IN ('FREE', 'PAID')",
            name="ck_activities_price_type",
        ),
        sa.CheckConstraint("end_at > start_at", name="ck_activities_time_range"),
        sa.ForeignKeyConstraint(
            ["organizer_id"],
            ["users.id"],
            name="fk_activities_organizer_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_activities_organizer_id",
        "activities",
        ["organizer_id"],
        unique=False,
    )
    op.create_index(
        "ix_activities_start_at",
        "activities",
        ["start_at"],
        unique=False,
    )
    op.create_index(
        "ix_activities_category",
        "activities",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_activities_location",
        "activities",
        ["location"],
        unique=False,
        postgresql_using="gist",
    )


def downgrade() -> None:
    op.drop_index("ix_activities_location", table_name="activities")
    op.drop_index("ix_activities_category", table_name="activities")
    op.drop_index("ix_activities_start_at", table_name="activities")
    op.drop_index("ix_activities_organizer_id", table_name="activities")
    op.drop_table("activities")
