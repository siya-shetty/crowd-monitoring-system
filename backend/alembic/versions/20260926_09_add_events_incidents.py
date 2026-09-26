"""Operational events and human-authored incidents."""
from alembic import op
import sqlalchemy as sa

revision = '20260926_09'
down_revision = '20260916_08'
branch_labels = None
depends_on = None


def common():
    return [sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('owner_id', sa.Uuid(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)]


def upgrade():
    op.create_table('operational_events', *common(),
        sa.Column('name', sa.String(120), nullable=False), sa.Column('description', sa.String(4000)),
        sa.Column('location', sa.String(200)), sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True)), sa.Column('status', sa.String(12), nullable=False),
        sa.CheckConstraint("status IN ('PLANNED','ACTIVE','COMPLETED','CANCELLED')", name='ck_event_status'),
        sa.CheckConstraint('end_time IS NULL OR end_time >= start_time', name='ck_event_times'))
    links = {'event_id':'operational_events', 'camera_id':'cameras', 'video_id':'videos',
             'live_session_id':'live_sessions', 'alert_event_id':'alert_events', 'live_alert_event_id':'live_alert_events'}
    op.create_table('incidents', *common(),
        sa.Column('title', sa.String(160), nullable=False), sa.Column('description', sa.String(4000), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False), sa.Column('status', sa.String(16), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False), sa.Column('resolved_at', sa.DateTime(timezone=True)),
        *[sa.Column(key, sa.Uuid(), sa.ForeignKey(table+'.id', ondelete='SET NULL')) for key, table in links.items()],
        sa.Column('context', sa.JSON(), nullable=False),
        sa.CheckConstraint("status IN ('OPEN','INVESTIGATING','RESOLVED','CLOSED')", name='ck_incident_status'),
        sa.CheckConstraint("severity IN ('INFO','WARNING','CRITICAL')", name='ck_incident_severity'),
        sa.CheckConstraint('alert_event_id IS NULL OR live_alert_event_id IS NULL', name='ck_incident_one_alert'),
        sa.CheckConstraint('resolved_at IS NULL OR resolved_at >= occurred_at', name='ck_incident_times'))
    op.create_index('ix_operational_events_owner_id', 'operational_events', ['owner_id'])
    for key in ['owner_id', 'severity', 'status', 'occurred_at', *links]:
        op.create_index('ix_incidents_'+key, 'incidents', [key])


def downgrade():
    op.drop_table('incidents')
    op.drop_table('operational_events')
