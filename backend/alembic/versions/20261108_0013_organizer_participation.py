"""Backfill automatic organizer participation for relevant legacy activities.

Eligibility uses the fixed UTC cutoff 2026-11-08 00:00:00+00, not the time an
operator reruns this migration. Activities ending exactly at/before that cutoff
or already cancelled are historical and receive no synthetic participation.
The two placement/confirmation timestamps record the database transaction time
of the actual insertion. No attendance or points are fabricated.

Existing participation rows, including inactive rows, are never rewritten.
Existing external participants are not demoted if adding the organizer takes
legacy occupancy above its configured limit.

Downgrade intentionally retains all data: without provenance, even an unchanged
CONFIRMED row cannot safely be identified as migration-created. In particular,
later check-ins, completion, photos, and points must survive a rollback.
"""

from alembic import op

revision = "20261108_0013"
down_revision = "20261031_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Lock parents before inserting child rows, matching application writers.
    # Ordering also gives concurrent runs one consistent parent lock order.
    op.execute(
        """
        WITH eligible_activities AS MATERIALIZED (
            SELECT a.id, a.organizer_id
            FROM activities AS a
            WHERE a.cancelled_at IS NULL
              AND a.end_at > TIMESTAMPTZ '2026-11-08 00:00:00+00'
              AND NOT EXISTS (
                  SELECT 1 FROM activity_participations AS p
                  WHERE p.activity_id = a.id AND p.user_id = a.organizer_id
              )
            ORDER BY a.id
            FOR UPDATE OF a
        )
        INSERT INTO activity_participations
            (activity_id, user_id, status, joined_at, confirmed_at)
        SELECT id, organizer_id, 'CONFIRMED',
               transaction_timestamp(), transaction_timestamp()
        FROM eligible_activities
        ON CONFLICT (activity_id, user_id) DO NOTHING
        """
    )


def downgrade() -> None:
    # This is a data-only revision. Retaining rows is deliberately safer than
    # guessing provenance and deleting genuine commitment/attendance evidence.
    pass
