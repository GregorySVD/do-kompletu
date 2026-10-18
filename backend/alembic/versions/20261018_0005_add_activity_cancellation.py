from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20261018_0005"
down_revision = "20261018_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activities",
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("activities", "cancelled_at")
