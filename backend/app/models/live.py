"""Camera configuration and bounded session snapshots; no captured media."""
import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Uuid, Integer, CheckConstraint, Index, text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Camera(Base):
    __tablename__ = 'cameras'
    __table_args__ = (CheckConstraint("source_type = 'BROWSER'", name='ck_camera_source'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(1000))
    source_type: Mapped[str] = mapped_column(String(20), default='BROWSER')
    source_configuration: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CameraZone(Base):
    __tablename__ = 'camera_zones'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cameras.id', ondelete='CASCADE'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(1000))
    polygon: Mapped[list] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class CameraRule(Base):
    __tablename__ = 'camera_rules'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cameras.id', ondelete='CASCADE'), index=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('camera_zones.id', ondelete='RESTRICT'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(1000))
    rule_type: Mapped[str] = mapped_column(String(40))
    scope: Mapped[str] = mapped_column(String(10))
    severity: Mapped[str] = mapped_column(String(10))
    enabled: Mapped[bool] = mapped_column(Boolean)
    configuration: Mapped[dict] = mapped_column(JSON)


ACTIVE = ('STARTING', 'RUNNING', 'STOPPING')


class LiveMonitoringSession(Base):
    __tablename__ = 'live_sessions'
    __table_args__ = (
        CheckConstraint("status IN ('STARTING','RUNNING','STOPPING','STOPPED','FAILED')", name='ck_live_status'),
        Index('uq_live_active_camera', 'camera_id', unique=True,
              postgresql_where=text("status IN ('STARTING','RUNNING','STOPPING')"),
              sqlite_where=text("status IN ('STARTING','RUNNING','STOPPING')")),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('users.id', ondelete='CASCADE'), index=True)
    camera_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('cameras.id', ondelete='CASCADE'), index=True)
    status: Mapped[str] = mapped_column(String(12), default='STARTING')
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_frame_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_frame_count: Mapped[int] = mapped_column(Integer, default=0)
    dropped_frame_count: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(String(300))
    latest_snapshot: Mapped[dict | None] = mapped_column(JSON)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class LiveAlertEvent(Base):
    __tablename__ = 'live_alert_events'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('live_sessions.id', ondelete='CASCADE'), index=True)
    rule_snapshot: Mapped[dict] = mapped_column(JSON)
    severity: Mapped[str] = mapped_column(String(10))
    evidence: Mapped[dict] = mapped_column(JSON)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
