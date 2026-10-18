from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261018_0004"
down_revision = "20260927_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_participations",
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["activity_id"],
            ["activities.id"],
            name="fk_activity_participations_activity_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_activity_participations_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "activity_id", "user_id", name="pk_activity_participations"
        ),
    )
    op.create_index(
        "ix_activity_participations_user_id", "activity_participations", ["user_id"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_activity_participations_user_id", table_name="activity_participations"
    )
    op.drop_table("activity_participations")
