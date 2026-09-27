"""Ownership, small immutable context snapshots, and explicit operator lifecycle."""
from datetime import datetime, timezone
from fastapi import HTTPException
from sqlalchemy import select
from app.models.live import Camera, LiveMonitoringSession, LiveAlertEvent
from app.models.video import Video
from app.models.alert import AlertEvent

LINKS = {'camera_id': (Camera, 'name'),
         'video_id': (Video, 'original_filename'), 'live_session_id': (LiveMonitoringSession, 'started_at')}


def owned(db, model, id, user, lock=False):
    query = select(model).where(model.id == id, model.owner_id == user.id)
    item = db.scalar(query.with_for_update(read=True, key_share=True) if lock else query)
    if item is None:
        raise HTTPException(404, 'Resource not found')
    return item


def alert_context(db, user, source, id, lock=False):
    model, parent = (AlertEvent, Video) if source == 'video' else (LiveAlertEvent, LiveMonitoringSession)
    query = select(model).join(parent).where(model.id == id, parent.owner_id == user.id)
    alert = db.scalar(query.with_for_update(read=True, key_share=True) if lock else query)
    if alert is None:
        raise HTTPException(404, 'Alert not found')
    rule = {'name': alert.rule_name, 'rule_type': alert.rule_type} if source == 'video' else alert.rule_snapshot
    snapshot = dict(id=str(alert.id), label=rule.get('name', 'Stored rule'),
        rule_type=rule.get('rule_type'), severity=alert.severity,
        zone=alert.evidence.get('zone_name'), recorded_at=alert.created_at.isoformat(), source=source)
    if source == 'video':
        snapshot['video_offset_seconds'] = alert.trigger_seconds
        links = dict(alert_event_id=alert.id, video_id=alert.video_id)
    else:
        session = owned(db, LiveMonitoringSession, alert.session_id, user, lock)
        links = dict(live_alert_event_id=alert.id, live_session_id=session.id, camera_id=session.camera_id)
    return snapshot, links


def prepare_incident(db, user, payload, previous=None):
    values = payload.model_dump()
    context = dict(previous.context) if previous else {}
    # Validate every explicit reference before enforcing contextual consistency.
    for key, (model, _) in LINKS.items():
        if values[key]:
            owned(db, model, values[key], user, True)
    for key, source in [('alert_event_id', 'video'), ('live_alert_event_id', 'live')]:
        context_key = key.removesuffix('_event_id')
        if values[key]:
            snapshot, implied = alert_context(db, user, source, values[key], True)
            context.pop('live_alert' if source == 'video' else 'alert', None)
            for link, id in implied.items():
                if values[link] and values[link] != id:
                    raise HTTPException(422, 'Alert context does not match linked resource')
                values[link] = id
            if previous is None or getattr(previous, key) != values[key]:
                context[context_key] = snapshot
        elif previous and getattr(previous, key) is not None:
            context.pop(context_key, None)
    if values['live_session_id']:
        session = owned(db, LiveMonitoringSession, values['live_session_id'], user, True)
        if values['camera_id'] and values['camera_id'] != session.camera_id:
            raise HTTPException(422, 'Camera does not match live session')
        values['camera_id'] = session.camera_id
    for key, (model, label) in LINKS.items():
        context_key = key.removesuffix('_id')
        if values[key]:
            item = owned(db, model, values[key], user, True)
            if previous is None or getattr(previous, key) != values[key]:
                context[context_key] = {'id': str(item.id), 'label': str(getattr(item, label))}
        elif previous and getattr(previous, key) is not None:
            context.pop(context_key, None)
    if values['status'] in ('RESOLVED', 'CLOSED'):
        values['resolved_at'] = values['resolved_at'] or datetime.now(timezone.utc)
        if values['resolved_at'] < values['occurred_at']:
            raise HTTPException(422, 'Resolution cannot precede occurrence')
    else:
        values['resolved_at'] = None
    return values | {'context': context}
