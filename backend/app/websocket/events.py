"""Explicit aggregate-only socket contracts. No tracks, frames or trajectories."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.models.live import LiveAlertEvent, ACTIVE
from app.core.config import get_settings
from app.websocket.manager import manager


class Metrics(BaseModel):
    sequence: int
    width: int
    height: int
    timestamp_seconds: float
    crowd_count_delta: int
    observed_crowd_count: int
    image_occupancy_ratio: float
    crowd_concentration: float
    crowd_level: Literal['LOW', 'MODERATE', 'HIGH', 'VERY_HIGH']
    crowd_trend: Literal['increasing', 'stable', 'decreasing']
    processing_duration_seconds: float
    current_operational_risk: Literal['NORMAL', 'ELEVATED', 'HIGH', 'CRITICAL']
    active_alert_count: int
    zones: dict[str, 'Zone']


class Zone(BaseModel):
    name: str
    active_tracks_in_zone: int
    active: bool = True
    peak: int = 0


class Alert(BaseModel):
    id: UUID
    rule_snapshot: dict
    severity: str
    evidence: dict
    created_at: datetime
    resolved_at: datetime | None
    model_config = {'from_attributes': True}


class State(BaseModel):
    id: UUID
    status: Literal['STARTING', 'RUNNING', 'STOPPING', 'STOPPED', 'FAILED']
    processed_frame_count: int
    dropped_frame_count: int
    last_frame_at: datetime | None
    is_stale: bool
    error_summary: str | None
    latest_snapshot: Metrics | None
    alerts: list[Alert] = Field(max_length=50)


class Event(BaseModel):
    version: Literal[1] = 1
    event: Literal['session.snapshot', 'session.stopped', 'session.failed', 'alert.triggered', 'alert.resolved']
    session_id: UUID
    sequence: int = 0
    emitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data: State
    alert: Alert | None = None


def publish(db, session, transitions=False):
    last = session.last_frame_at or session.started_at
    metrics = None
    if session.latest_snapshot:
        snapshot = dict(session.latest_snapshot)
        existing = snapshot.get('zones', {})
        peaks = session.summary.get('zone_peak_counts', {})
        snapshot['zones'] = {z['id']: dict(name=z['name'], active=z['active'],
            active_tracks_in_zone=existing.get(z['id'], {}).get('active_tracks_in_zone', 0),
            peak=peaks.get(z['id'], 0)) for z in session.summary.get('zones', [])}
        metrics = Metrics.model_validate(snapshot)
    alerts = list(db.scalars(select(LiveAlertEvent).where(LiveAlertEvent.session_id == session.id)
        .order_by(LiveAlertEvent.resolved_at.is_not(None), LiveAlertEvent.created_at.desc()).limit(50)))
    state = State(id=session.id, status=session.status,
        processed_frame_count=session.processed_frame_count, dropped_frame_count=session.dropped_frame_count,
        last_frame_at=session.last_frame_at, error_summary=session.error_summary,
        is_stale=session.status in ACTIVE and (datetime.now(timezone.utc)-last).total_seconds() > get_settings().live_session_stale_seconds,
        latest_snapshot=metrics,
        alerts=[Alert.model_validate(a) for a in alerts])
    kind = {'STOPPED':'session.stopped', 'FAILED':'session.failed'}.get(session.status, 'session.snapshot')
    events = []
    observation = session.latest_snapshot or {}
    for name, key in [('alert.triggered','triggered_alert_ids'), ('alert.resolved','resolved_alert_ids')]:
        for alert in state.alerts:
            if transitions and str(alert.id) in observation.get(key, []):
                events.append(Event(event=name, session_id=session.id, data=state, alert=alert))
    events.append(Event(event=kind, session_id=session.id, data=state))
    manager.publish(session.id, events)
