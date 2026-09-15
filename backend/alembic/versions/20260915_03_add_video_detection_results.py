"""add persisted person detection results

Revision ID: 20260915_03
Revises: 20260915_02
"""
from alembic import op
import sqlalchemy as sa

revision = "20260915_03"
down_revision = "20260915_02"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("videos", sa.Column("detection_summary", sa.JSON(), nullable=True))
    op.add_column("videos", sa.Column("detection_frames", sa.JSON(), nullable=True))
    op.add_column("videos", sa.Column("preview_storage_key", sa.String(length=255), nullable=True))

def downgrade() -> None:
    op.drop_column("videos", "preview_storage_key")
    op.drop_column("videos", "detection_frames")
    op.drop_column("videos", "detection_summary")
