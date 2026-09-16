import uuid
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, JSON, String, Uuid, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class AlertRule(Base):
    __tablename__ = 'alert_rules'
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('videos.id', ondelete='CASCADE'), index=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('monitoring_zones.id', ondelete='RESTRICT'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(1000))
    rule_type: Mapped[str] = mapped_column(String(40), index=True)
    scope: Mapped[str] = mapped_column(String(10))
    severity: Mapped[str] = mapped_column(String(10))
    enabled: Mapped[bool] = mapped_column(Boolean, index=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AlertEvent(Base):
    __tablename__ = 'alert_events'
    __table_args__ = (UniqueConstraint('rule_id', 'condition_start_seconds', name='uq_alert_rule_interval'),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('alert_rules.id', ondelete='SET NULL'), index=True)
    video_id: Mapped[uuid.UUID] = mapped_column(ForeignKey('videos.id', ondelete='CASCADE'), index=True)
    zone_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey('monitoring_zones.id', ondelete='SET NULL'), index=True)
    rule_name: Mapped[str] = mapped_column(String(100))
    rule_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10), index=True)
    configuration: Mapped[dict] = mapped_column(JSON)
    condition_start_seconds: Mapped[float] = mapped_column(Float, index=True)
    trigger_seconds: Mapped[float] = mapped_column(Float)
    end_seconds: Mapped[float] = mapped_column(Float)
    state: Mapped[str] = mapped_column(String(20), default='HISTORICAL')
    evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
