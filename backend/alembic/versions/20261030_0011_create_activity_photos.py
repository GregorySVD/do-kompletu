"""Private gallery metadata; image objects live outside PostgreSQL."""

import sqlalchemy as sa

from alembic import op

revision = "20261030_0011"
down_revision = "20261019_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("uploader_id", sa.Uuid(), nullable=False),
        sa.Column("object_key", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["activity_id"], ["activities.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("object_key"),
        sa.CheckConstraint(
            "size_bytes BETWEEN 1 AND 10485760", name="ck_activity_photos_size"
        ),
        sa.CheckConstraint(
            "content_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="ck_activity_photos_content_type",
        ),
    )
    op.create_index(
        "ix_activity_photos_activity_uploader",
        "activity_photos",
        ["activity_id", "uploader_id"],
    )
    op.create_index(
        "ix_activity_photos_uploader_id", "activity_photos", ["uploader_id"]
    )


def downgrade() -> None:
    # Intentionally loses gallery metadata, never deletes external objects.
    op.drop_table("activity_photos")
