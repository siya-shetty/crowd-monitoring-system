"""Persist versioned image-space crowd analytics; old results remain readable."""
from alembic import op
import sqlalchemy as sa

revision = "20260915_05"
down_revision = "20260915_04"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("videos", sa.Column("crowd_analysis", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("videos", "crowd_analysis")
