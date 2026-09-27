"""Operator-authored records; optional monitoring links never own incidents."""
import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class OperationalEvent(Base):
    # Legacy mapping retained for migration metadata and historical incident FKs.
    # Events have no active API or application workflow.
    __tablename__ = 'operational_events'
    __table_args__ = (
        CheckConstraint("status IN ('PLANNED','ACTIVE','COMPLETED','CANCELLED')", name='ck_event_status'),
        CheckConstraint('end_time IS NULL OR end_time >= start_time', name='ck_event_times'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(String(4000))
    location: Mapped[str | None] = mapped_column(String(200))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(12), default='PLANNED')
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Incident(Base):
    __tablename__ = 'incidents'
    __table_args__ = (
        CheckConstraint("status IN ('OPEN','INVESTIGATING','RESOLVED','CLOSED')", name='ck_incident_status'),
        CheckConstraint("severity IN ('INFO','WARNING','CRITICAL')", name='ck_incident_severity'),
        CheckConstraint('alert_event_id IS NULL OR live_alert_event_id IS NULL', name='ck_incident_one_alert'),
        CheckConstraint('resolved_at IS NULL OR resolved_at >= occurred_at', name='ck_incident_times'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(4000), default='')
    severity: Mapped[str] = mapped_column(String(10), default='WARNING', index=True)
    status: Mapped[str] = mapped_column(String(16), default='OPEN', index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Preserve historical links; incident writes no longer accept this field.
    event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('operational_events.id', ondelete='SET NULL'), index=True)
    camera_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('cameras.id', ondelete='SET NULL'), index=True)
    video_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('videos.id', ondelete='SET NULL'), index=True)
    live_session_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('live_sessions.id', ondelete='SET NULL'), index=True)
    alert_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('alert_events.id', ondelete='SET NULL'), index=True)
    live_alert_event_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('live_alert_events.id', ondelete='SET NULL'), index=True)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
