"""Persist observation heatmaps and video-owned monitoring polygons."""
from alembic import op
import sqlalchemy as sa

revision = "20260916_06"
down_revision = "20260915_05"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("videos", sa.Column("heatmap_analysis", sa.JSON(), nullable=True))
    op.create_table("monitoring_zones",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("video_id", sa.Uuid(), sa.ForeignKey("videos.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("polygon", sa.JSON(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("analysis", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.create_index("ix_monitoring_zones_video_id", "monitoring_zones", ["video_id"])


def downgrade():
    op.drop_table("monitoring_zones")
    op.drop_column("videos", "heatmap_analysis")
