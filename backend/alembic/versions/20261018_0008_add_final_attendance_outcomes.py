"""Add terminal attendance outcomes without changing existing participation."""

import sqlalchemy as sa

from alembic import op

revision = "20261018_0008"
down_revision = "20261018_0007"
branch_labels = None
depends_on = None

TABLE = "activity_participations"
STATUS_CHECK = "ck_activity_participations_status"
TIMESTAMPS_CHECK = "ck_activity_participations_state_timestamps"


def upgrade() -> None:
    op.add_column(
        TABLE, sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        TABLE, sa.Column("no_show_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.drop_constraint(TIMESTAMPS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    op.create_check_constraint(
        STATUS_CHECK,
        TABLE,
        "status IN ('JOINED', 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW', 'LEFT')",
    )
    op.create_check_constraint(
        TIMESTAMPS_CHECK,
        TABLE,
        "(status = 'JOINED' AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
        "(status = 'CONFIRMED' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
        "(status = 'CHECKED_IN' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
        "(status = 'COMPLETED' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NOT NULL AND no_show_at IS NULL) OR "
        "(status = 'NO_SHOW' AND left_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NOT NULL) OR "
        "(status = 'LEFT' AND left_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint(TIMESTAMPS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    op.execute(
        "UPDATE activity_participations SET status = 'CHECKED_IN' WHERE status = 'COMPLETED'"
    )
    # NO_SHOW may originate from JOINED. Do not fabricate confirmation evidence
    # merely to satisfy the old CONFIRMED timestamp constraint.
    op.execute(
        "UPDATE activity_participations SET status = CASE WHEN confirmed_at IS NULL THEN 'JOINED' ELSE 'CONFIRMED' END WHERE status = 'NO_SHOW'"
    )
    op.drop_column(TABLE, "completed_at")
    op.drop_column(TABLE, "no_show_at")
    op.create_check_constraint(
        STATUS_CHECK, TABLE, "status IN ('JOINED', 'CONFIRMED', 'CHECKED_IN', 'LEFT')"
    )
    op.create_check_constraint(
        TIMESTAMPS_CHECK,
        TABLE,
        "(status = 'JOINED' AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL) OR "
        "(status = 'CONFIRMED' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NULL) OR "
        "(status = 'CHECKED_IN' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL) OR "
        "(status = 'LEFT' AND left_at IS NOT NULL AND checked_in_at IS NULL)",
    )
