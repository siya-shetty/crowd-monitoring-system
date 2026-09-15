"""Persist anonymous per-video tracking; existing detections remain unchanged."""
from alembic import op
import sqlalchemy as sa

revision = "20260915_04"
down_revision = "20260915_03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("tracking_analysis", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "tracking_analysis")
