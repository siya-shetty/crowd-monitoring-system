"""Browser cameras and live session history, independent of uploaded videos."""
from alembic import op
import sqlalchemy as sa

revision = '20260916_08'
down_revision = '20260916_07'
branch_labels = None
depends_on = None


def identifier():
    return sa.Column('id', sa.Uuid(), primary_key=True)


def timestamps():
    return [sa.Column(k, sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
            for k in ('created_at', 'updated_at')]


def upgrade():
    op.create_table('cameras', identifier(),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False), sa.Column('description', sa.String(1000)),
        sa.Column('source_type', sa.String(20), nullable=False),
        sa.Column('source_configuration', sa.JSON(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False), *timestamps(),
        sa.CheckConstraint("source_type = 'BROWSER'", name='ck_camera_source'))
    op.create_table('camera_zones', identifier(),
        sa.Column('camera_id', sa.Uuid(), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False), sa.Column('description', sa.String(1000)),
        sa.Column('polygon', sa.JSON(), nullable=False), sa.Column('active', sa.Boolean(), nullable=False))
    op.create_table('camera_rules', identifier(),
        sa.Column('camera_id', sa.Uuid(), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zone_id', sa.Uuid(), sa.ForeignKey('camera_zones.id', ondelete='RESTRICT')),
        sa.Column('name', sa.String(100), nullable=False), sa.Column('description', sa.String(1000)),
        sa.Column('rule_type', sa.String(40), nullable=False), sa.Column('scope', sa.String(10), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False), sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False))
    op.create_table('live_sessions', identifier(),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('camera_id', sa.Uuid(), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('stopped_at', sa.DateTime(timezone=True)), sa.Column('last_frame_at', sa.DateTime(timezone=True)),
        sa.Column('processed_frame_count', sa.Integer(), nullable=False),
        sa.Column('dropped_frame_count', sa.Integer(), nullable=False), sa.Column('error_summary', sa.String(300)),
        sa.Column('latest_snapshot', sa.JSON()), sa.Column('summary', sa.JSON(), nullable=False), *timestamps(),
        sa.CheckConstraint("status IN ('STARTING','RUNNING','STOPPING','STOPPED','FAILED')", name='ck_live_status'))
    op.create_index('uq_live_active_camera', 'live_sessions', ['camera_id'], unique=True,
        postgresql_where=sa.text("status IN ('STARTING','RUNNING','STOPPING')"))
    op.create_table('live_alert_events', identifier(),
        sa.Column('session_id', sa.Uuid(), sa.ForeignKey('live_sessions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('rule_snapshot', sa.JSON(), nullable=False), sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False), sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    for table, columns in {'cameras': ['owner_id'], 'camera_zones': ['camera_id'],
            'camera_rules': ['camera_id', 'zone_id'], 'live_sessions': ['owner_id', 'camera_id'],
            'live_alert_events': ['session_id']}.items():
        for column in columns:
            op.create_index('ix_'+table+'_'+column, table, [column])


def downgrade():
    for table in ('live_alert_events', 'live_sessions', 'camera_rules', 'camera_zones', 'cameras'):
        op.drop_table(table)
