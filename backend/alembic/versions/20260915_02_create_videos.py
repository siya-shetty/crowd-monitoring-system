"""create videos table"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="20260915_02"; down_revision="20260915_01"; branch_labels=None; depends_on=None
video_status=postgresql.ENUM("uploaded","processing","completed","failed",name="video_status",create_type=False)
def upgrade()->None:
    video_status.create(op.get_bind(),checkfirst=True)
    op.create_table("videos",sa.Column("id",sa.Uuid(),primary_key=True),sa.Column("owner_id",sa.Uuid(),sa.ForeignKey("users.id",ondelete="CASCADE"),nullable=False),sa.Column("original_filename",sa.String(255),nullable=False),sa.Column("storage_key",sa.String(255),nullable=False,unique=True),sa.Column("content_type",sa.String(100),nullable=False),sa.Column("file_size",sa.Integer(),nullable=False),sa.Column("status",video_status,nullable=False,server_default="uploaded"),sa.Column("duration_seconds",sa.Float()),sa.Column("width",sa.Integer()),sa.Column("height",sa.Integer()),sa.Column("fps",sa.Float()),sa.Column("frame_count",sa.Integer()),sa.Column("error_message",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),server_default=sa.text("now()"),nullable=False),sa.Column("processing_started_at",sa.DateTime(timezone=True)),sa.Column("processing_completed_at",sa.DateTime(timezone=True)));op.create_index("ix_videos_owner_id","videos",["owner_id"])
def downgrade()->None: op.drop_index("ix_videos_owner_id",table_name="videos");op.drop_table("videos");video_status.drop(op.get_bind(),checkfirst=True)
