import csv
import io
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.api.v1.dependencies import DatabaseSession
from app.api.v1.videos import CurrentUser
from app.models.operations import Incident
from app.models.video import Video
from app.models.live import Camera, LiveMonitoringSession
from app.schemas.operations import IncidentInput, IncidentResponse, IncidentStatus
from app.schemas.alerts import Severity
from app.services.operations import owned, alert_context, prepare_incident

router = APIRouter(tags=['operations'])


def save(db, item):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Linked resource changed; refresh and try again') from None
    db.refresh(item)
    return item


def incident_query(db, user, status, severity):
    query = select(Incident).where(Incident.owner_id == user.id)
    if status:
        query = query.where(Incident.status == status)
    if severity:
        query = query.where(Incident.severity == severity)
    return query.order_by(Incident.occurred_at.desc(), Incident.id)


@router.get('/incidents', response_model=list[IncidentResponse])
def incidents(db: DatabaseSession, user: CurrentUser, status: IncidentStatus | None = None,
              severity: Severity | None = None, offset: int = Query(default=0, ge=0)):
    return list(db.scalars(incident_query(db, user, status, severity).offset(offset).limit(200)))


@router.get('/incidents/options')
def options(db: DatabaseSession, user: CurrentUser):
    # Small projections avoid the existing video endpoint's large analysis payloads.
    def rows(model, label, order):
        return [dict(id=str(id), label=str(name)) for id, name in db.execute(
            select(model.id, label).where(model.owner_id == user.id).order_by(order.desc(), model.id).limit(200))]
    return dict(cameras=rows(Camera, Camera.name, Camera.created_at),
        videos=rows(Video, Video.original_filename, Video.created_at),
        sessions=[dict(id=str(id), label=f'{name} / {started.isoformat()}', camera_id=str(camera_id))
            for id, name, started, camera_id in db.execute(select(LiveMonitoringSession.id, Camera.name,
                LiveMonitoringSession.started_at, LiveMonitoringSession.camera_id).join(Camera)
                .where(LiveMonitoringSession.owner_id == user.id).order_by(LiveMonitoringSession.started_at.desc(), LiveMonitoringSession.id).limit(200))])


@router.get('/incidents/alert-context')
def from_alert(db: DatabaseSession, user: CurrentUser, source: Literal['video', 'live'], alert_id: UUID):
    snapshot, links = alert_context(db, user, source, alert_id)
    return dict(title=f"Review: {snapshot['label']}"[:160], severity=snapshot['severity'],
        description=f"Operator review of {snapshot['rule_type']} alert. Zone: {snapshot['zone'] or 'whole source'}.",
        occurred_at=snapshot['recorded_at'] if source == 'live' else None,
        context=snapshot, **links)


def safe_cell(value):
    value = '' if value is None else str(value)
    # CSV quoting alone does not prevent spreadsheet formula execution.
    if value[:1] in ('\t', '\r', '\n') or value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


@router.get('/incidents/export.csv')
def export(db: DatabaseSession, user: CurrentUser, status: IncidentStatus | None = None,
           severity: Severity | None = None):
    items = list(db.scalars(incident_query(db, user, status, severity).limit(10001)))
    if len(items) > 10000:
        raise HTTPException(413, 'Report exceeds 10000 rows; filter by status or severity')
    output = io.StringIO(newline='')
    writer = csv.writer(output, quoting=csv.QUOTE_ALL)
    writer.writerow(['incident_id', 'title', 'description', 'severity', 'status', 'occurred_at', 'resolved_at',
        'camera', 'video', 'session', 'alert_rule', 'alert_type', 'alert_severity', 'alert_zone',
        'alert_recorded_at', 'video_offset_seconds', 'camera_id', 'video_id', 'live_session_id',
        'alert_event_id', 'live_alert_event_id'])
    for item in items:
        ctx = item.context
        alert = ctx.get('alert') or ctx.get('live_alert') or {}
        row = [item.id, item.title, item.description, item.severity, item.status, item.occurred_at.isoformat(),
            item.resolved_at.isoformat() if item.resolved_at else None,
            *[ctx.get(key, {}).get('label') for key in ('camera', 'video', 'live_session')],
            *[alert.get(key) for key in ('label', 'rule_type', 'severity', 'zone', 'recorded_at', 'video_offset_seconds')],
            *[getattr(item, key) for key in ('camera_id', 'video_id', 'live_session_id', 'alert_event_id', 'live_alert_event_id')]]
        writer.writerow([safe_cell(value) for value in row])
    return Response('\ufeff'+output.getvalue(), media_type='text/csv; charset=utf-8', headers={
        'Content-Disposition': 'attachment; filename="incidents.csv"', 'Cache-Control': 'no-store',
        'X-Content-Type-Options': 'nosniff'})


@router.post('/incidents', response_model=IncidentResponse, status_code=201)
def create_incident(payload: IncidentInput, db: DatabaseSession, user: CurrentUser):
    item = Incident(owner_id=user.id, **prepare_incident(db, user, payload))
    db.add(item)
    return save(db, item)


@router.get('/incidents/{id}', response_model=IncidentResponse)
def incident(id: UUID, db: DatabaseSession, user: CurrentUser):
    return owned(db, Incident, id, user)


@router.put('/incidents/{id}', response_model=IncidentResponse)
def update_incident(id: UUID, payload: IncidentInput, db: DatabaseSession, user: CurrentUser):
    item = owned(db, Incident, id, user)
    for key, value in prepare_incident(db, user, payload, item).items():
        setattr(item, key, value)
    return save(db, item)


@router.delete('/incidents/{id}', status_code=204)
def delete_incident(id: UUID, db: DatabaseSession, user: CurrentUser):
    db.delete(owned(db, Incident, id, user))
    db.commit()
