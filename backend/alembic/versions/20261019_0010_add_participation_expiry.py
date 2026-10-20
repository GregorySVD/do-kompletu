"""Add system participation expiry while preserving existing rows and attendance."""

import sqlalchemy as sa

from alembic import op

revision = "20261019_0010"
down_revision = "20261018_0009"
branch_labels = None
depends_on = None

TABLE = "activity_participations"
STATUS_CHECK = "ck_activity_participations_status"
TIMESTAMPS_CHECK = "ck_activity_participations_state_timestamps"
OLD_TIMESTAMPS = "(status = 'WAITLISTED' AND waitlisted_at IS NOT NULL AND joined_at IS NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'JOINED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'CONFIRMED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'CHECKED_IN' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'COMPLETED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NOT NULL AND no_show_at IS NULL) OR (status = 'NO_SHOW' AND joined_at IS NOT NULL AND left_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NOT NULL) OR (status = 'LEFT' AND (joined_at IS NOT NULL OR (waitlisted_at IS NOT NULL AND confirmed_at IS NULL)) AND left_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL)"
NEW_TIMESTAMPS = "(confirmation_expired_at IS NULL AND waitlist_expired_at IS NULL AND ((status = 'WAITLISTED' AND waitlisted_at IS NOT NULL AND joined_at IS NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'JOINED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'CONFIRMED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'CHECKED_IN' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'COMPLETED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NOT NULL AND no_show_at IS NULL) OR (status = 'NO_SHOW' AND joined_at IS NOT NULL AND left_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NOT NULL) OR (status = 'LEFT' AND (joined_at IS NOT NULL OR (waitlisted_at IS NOT NULL AND confirmed_at IS NULL)) AND left_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL))) OR (status = 'CONFIRMATION_EXPIRED' AND joined_at IS NOT NULL AND confirmation_expired_at IS NOT NULL AND waitlist_expired_at IS NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR (status = 'WAITLIST_EXPIRED' AND waitlisted_at IS NOT NULL AND joined_at IS NULL AND waitlist_expired_at IS NOT NULL AND confirmation_expired_at IS NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL)"


def upgrade() -> None:
    op.add_column(
        TABLE, sa.Column("confirmation_expired_at", sa.DateTime(timezone=True))
    )
    op.add_column(TABLE, sa.Column("waitlist_expired_at", sa.DateTime(timezone=True)))
    op.drop_constraint(TIMESTAMPS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    # CONFIRMATION_EXPIRED exceeds the old VARCHAR(16). No existing value changes.
    op.alter_column(
        TABLE,
        "status",
        existing_type=sa.String(16),
        type_=sa.String(24),
        existing_nullable=False,
    )
    op.create_check_constraint(
        STATUS_CHECK,
        TABLE,
        "status IN ('CONFIRMATION_EXPIRED', 'WAITLIST_EXPIRED', 'WAITLISTED', 'JOINED', 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW', 'LEFT')",
    )
    op.create_check_constraint(TIMESTAMPS_CHECK, TABLE, NEW_TIMESTAMPS)


def downgrade() -> None:
    op.drop_constraint(TIMESTAMPS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    # Preserve inactive occupancy and rows, losing automatic-vs-voluntary intent.
    op.execute(
        "UPDATE activity_participations SET status = 'LEFT', left_at = confirmation_expired_at WHERE status = 'CONFIRMATION_EXPIRED'"
    )
    # 0009 can retain the original queue entry; no join/attendance is fabricated.
    op.execute(
        "UPDATE activity_participations SET status = 'WAITLISTED' WHERE status = 'WAITLIST_EXPIRED'"
    )
    op.drop_column(TABLE, "confirmation_expired_at")
    op.drop_column(TABLE, "waitlist_expired_at")
    op.alter_column(
        TABLE,
        "status",
        existing_type=sa.String(24),
        type_=sa.String(16),
        existing_nullable=False,
    )
    op.create_check_constraint(
        STATUS_CHECK,
        TABLE,
        "status IN ('WAITLISTED', 'JOINED', 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW', 'LEFT')",
    )
    op.create_check_constraint(TIMESTAMPS_CHECK, TABLE, OLD_TIMESTAMPS)
