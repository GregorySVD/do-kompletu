"""Retain participation lifecycle and attendance confirmation metadata."""

import sqlalchemy as sa

from alembic import op

revision = "20261018_0006"
down_revision = "20261018_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # A server default backfills existing memberships as JOINED, without duplicates.
    op.add_column(
        "activity_participations",
        sa.Column(
            "status",
            sa.String(16),
            nullable=False,
            server_default="JOINED",
        ),
    )
    op.add_column(
        "activity_participations",
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "activity_participations",
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_activity_participations_status",
        "activity_participations",
        "status IN ('JOINED', 'CONFIRMED', 'LEFT')",
    )
    op.create_check_constraint(
        "ck_activity_participations_state_timestamps",
        "activity_participations",
        "(status = 'JOINED' AND left_at IS NULL AND confirmed_at IS NULL) OR "
        "(status = 'CONFIRMED' AND left_at IS NULL AND confirmed_at IS NOT NULL) OR "
        "(status = 'LEFT' AND left_at IS NOT NULL)",
    )


def downgrade() -> None:
    # The old schema equates row existence with membership. Remove inactive rows
    # rather than silently reactivating users who left; other lifecycle data is lost.
    op.execute("DELETE FROM activity_participations WHERE status = 'LEFT'")
    op.drop_constraint(
        "ck_activity_participations_state_timestamps",
        "activity_participations",
        type_="check",
    )
    op.drop_constraint(
        "ck_activity_participations_status", "activity_participations", type_="check"
    )
    op.drop_column("activity_participations", "confirmed_at")
    op.drop_column("activity_participations", "left_at")
    op.drop_column("activity_participations", "status")
