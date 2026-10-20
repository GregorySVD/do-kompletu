"""Add FIFO waitlists without assigning an active join time to queued users."""

import sqlalchemy as sa

from alembic import op

revision = "20261018_0009"
down_revision = "20261018_0008"
branch_labels = None
depends_on = None

TABLE = "activity_participations"
STATUS_CHECK = "ck_activity_participations_status"
TIMESTAMPS_CHECK = "ck_activity_participations_state_timestamps"
FIFO_INDEX = "ix_activity_participations_fifo"

OLD_TIMESTAMPS = (
    "(status = 'JOINED' AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
    "(status = 'CONFIRMED' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
    "(status = 'CHECKED_IN' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
    "(status = 'COMPLETED' AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NOT NULL AND no_show_at IS NULL) OR "
    "(status = 'NO_SHOW' AND left_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NOT NULL) OR "
    "(status = 'LEFT' AND left_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL)"
)
NEW_TIMESTAMPS = (
    "(status = 'WAITLISTED' AND waitlisted_at IS NOT NULL AND joined_at IS NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
    "(status = 'JOINED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
    "(status = 'CONFIRMED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
    "(status = 'CHECKED_IN' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NULL AND no_show_at IS NULL) OR "
    "(status = 'COMPLETED' AND joined_at IS NOT NULL AND left_at IS NULL AND confirmed_at IS NOT NULL AND checked_in_at IS NOT NULL AND completed_at IS NOT NULL AND no_show_at IS NULL) OR "
    "(status = 'NO_SHOW' AND joined_at IS NOT NULL AND left_at IS NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NOT NULL) OR "
    "(status = 'LEFT' AND (joined_at IS NOT NULL OR (waitlisted_at IS NOT NULL AND confirmed_at IS NULL)) AND left_at IS NOT NULL AND checked_in_at IS NULL AND completed_at IS NULL AND no_show_at IS NULL)"
)


def upgrade() -> None:
    op.add_column(TABLE, sa.Column("waitlisted_at", sa.DateTime(timezone=True)))
    op.drop_constraint(TIMESTAMPS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    # Keep the JOINED server default for backwards-compatible direct inserts.
    # Explicit NULL is required for WAITLISTED, enforced by the state CHECK.
    op.alter_column(TABLE, "joined_at", nullable=True)
    op.create_check_constraint(
        STATUS_CHECK,
        TABLE,
        "status IN ('WAITLISTED', 'JOINED', 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW', 'LEFT')",
    )
    op.create_check_constraint(TIMESTAMPS_CHECK, TABLE, NEW_TIMESTAMPS)
    # Activity/status equality followed by FIFO order; also covers state counts.
    # See activity-waitlist.md for the representative PostgreSQL plan validation.
    op.create_index(
        FIFO_INDEX, TABLE, ["activity_id", "status", "waitlisted_at", "user_id"]
    )


def downgrade() -> None:
    op.drop_index(FIFO_INDEX, table_name=TABLE)
    op.drop_constraint(TIMESTAMPS_CHECK, TABLE, type_="check")
    op.drop_constraint(STATUS_CHECK, TABLE, type_="check")
    # 0008 has no queue and mandates joined_at on every retained row. Preserve
    # queued records as inactive LEFT, never as attendance or active occupancy.
    # For never-joined rows ONLY, the legacy joined_at carries queue-entry time;
    # this is a documented lossy downgrade, not the 0009 joined_at semantics.
    # Already-LEFT queue departures keep their true left_at. Active/final rows
    # (including promoted users) retain every existing timestamp and status.
    op.execute(
        "UPDATE activity_participations SET "
        "joined_at = COALESCE(joined_at, waitlisted_at), "
        "left_at = CASE WHEN status = 'WAITLISTED' THEN CURRENT_TIMESTAMP ELSE left_at END, "
        "status = CASE WHEN status = 'WAITLISTED' THEN 'LEFT' ELSE status END "
        "WHERE status = 'WAITLISTED' OR joined_at IS NULL"
    )
    op.alter_column(TABLE, "joined_at", nullable=False)
    op.drop_column(TABLE, "waitlisted_at")
    op.create_check_constraint(
        STATUS_CHECK,
        TABLE,
        "status IN ('JOINED', 'CONFIRMED', 'CHECKED_IN', 'COMPLETED', 'NO_SHOW', 'LEFT')",
    )
    op.create_check_constraint(TIMESTAMPS_CHECK, TABLE, OLD_TIMESTAMPS)
