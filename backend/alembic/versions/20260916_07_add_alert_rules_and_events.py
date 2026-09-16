"""Persist rule configuration and bounded historical alert intervals."""
from alembic import op
import sqlalchemy as sa

revision = '20260916_07'
down_revision = '20260916_06'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('alert_rules',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('video_id', sa.Uuid(), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zone_id', sa.Uuid(), sa.ForeignKey('monitoring_zones.id', ondelete='RESTRICT')),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(1000)),
        sa.Column('rule_type', sa.String(40), nullable=False),
        sa.Column('scope', sa.String(10), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("severity IN ('INFO','WARNING','CRITICAL')", name='ck_rule_severity'),
        sa.CheckConstraint("(scope='VIDEO' AND zone_id IS NULL AND rule_type IN ('CROWD_COUNT_ABOVE','CROWD_LEVEL_AT_LEAST','SUDDEN_CROWD_INCREASE')) OR (scope='ZONE' AND zone_id IS NOT NULL AND rule_type IN ('ZONE_COUNT_ABOVE','ZONE_PRESENCE'))", name='ck_rule_scope'))
    for column in ('video_id', 'zone_id', 'enabled', 'rule_type'):
        op.create_index('ix_alert_rules_'+column, 'alert_rules', [column])
    op.create_table('alert_events',
        sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('rule_id', sa.Uuid(), sa.ForeignKey('alert_rules.id', ondelete='SET NULL')),
        sa.Column('video_id', sa.Uuid(), sa.ForeignKey('videos.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zone_id', sa.Uuid(), sa.ForeignKey('monitoring_zones.id', ondelete='SET NULL')),
        sa.Column('rule_name', sa.String(100), nullable=False),
        sa.Column('rule_type', sa.String(40), nullable=False),
        sa.Column('severity', sa.String(10), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('condition_start_seconds', sa.Float(), nullable=False),
        sa.Column('trigger_seconds', sa.Float(), nullable=False),
        sa.Column('end_seconds', sa.Float(), nullable=False),
        sa.Column('state', sa.String(20), nullable=False),
        sa.Column('evidence', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('rule_id', 'condition_start_seconds', name='uq_alert_rule_interval'),
        sa.CheckConstraint('condition_start_seconds >= 0 AND trigger_seconds >= condition_start_seconds AND end_seconds >= trigger_seconds', name='ck_event_times'),
        sa.CheckConstraint("severity IN ('INFO','WARNING','CRITICAL')", name='ck_event_severity'))
    for column in ('video_id', 'rule_id', 'zone_id', 'severity', 'condition_start_seconds'):
        op.create_index('ix_alert_events_'+column, 'alert_events', [column])


def downgrade():
    op.drop_table('alert_events')
    op.drop_table('alert_rules')
