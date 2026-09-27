from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260927_0002"
down_revision = "20260830_0001"
branch_labels = None
depends_on = None

INDEX_NAME = "uq_users_display_name_lower"


def upgrade() -> None:
    op.create_index(
        INDEX_NAME,
        "users",
        [sa.text("lower(display_name)")],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(INDEX_NAME, table_name="users")
