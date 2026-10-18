"""Add checked-in participation without storing participant coordinates."""

import sqlalchemy as sa

from alembic import op

revision = "20261018_0007"
down_revision = "20261018_0006"
branch_labels = None
depends_on = None

STATUS_CHECK = "ck_activity_participations_status"
TIMESTAMPS_CHECK = "ck_activity_participations_state_timestamps"
TABLE = "activity_participations"


def upgrade() -> None:
    op.add_column(
        TABLE, sa.Column("checked_in_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.drop_constraint(TIMESTAMPS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
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


def downgrade() -> None:
    op.drop_constraint(TIMESTAMPS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    # Preserve the row and its confirmation; only check-in evidence is lost.
    op.execute(
        "UPDATE activity_participations SET status = 'CONFIRMED' WHERE status = 'CHECKED_IN'"
    )
    op.drop_column(TABLE, "checked_in_at")
    op.create_check_constraint(
        STATUS_CHECK, TABLE, "status IN ('JOINED', 'CONFIRMED', 'LEFT')"
    )
    op.create_check_constraint(
        TIMESTAMPS_CHECK,
        TABLE,
        "(status = 'JOINED' AND left_at IS NULL AND confirmed_at IS NULL) OR "
        "(status = 'CONFIRMED' AND left_at IS NULL AND confirmed_at IS NOT NULL) OR "
        "(status = 'LEFT' AND left_at IS NOT NULL)",
    )
