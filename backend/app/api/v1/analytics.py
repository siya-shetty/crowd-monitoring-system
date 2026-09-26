from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app.api.v1.dependencies import DatabaseSession
from app.api.v1.videos import CurrentUser
from app.models.video import Video
from app.models.zone import MonitoringZone
from app.models.alert import AlertEvent
from app.models.live import Camera, LiveMonitoringSession as Session, LiveAlertEvent
from app.services.analytics import aggregate, breakdown, session_data, utc
from app.services.alert_engine import operational_risk

router = APIRouter(prefix='/analytics', tags=['analytics'])


def session_query():
    # Exclude individual tracks from historical analytics queries.
    return select(Session.id, Session.status, Session.started_at, Session.stopped_at,
        Session.processed_frame_count, Session.dropped_frame_count, Session.summary,
        Session.latest_snapshot['current_operational_risk'].label('final_risk'),
        Camera.name.label('camera_name')).join(Camera)


def session_row(row):
    values = dict(row._mapping)
    name = values.pop('camera_name')
    values['latest_snapshot'] = {'current_operational_risk': values.pop('final_risk')}
    return SimpleNamespace(**values), name


@router.get('')
def overview(db: DatabaseSession, user: CurrentUser, response: Response,
             range: Literal['7d', '30d', 'all'] = '30d'):
    response.headers['Cache-Control'] = 'no-store'
    end = datetime.now(timezone.utc)
    start = end-timedelta(days=7 if range == '7d' else 30) if range != 'all' else None
    vf = [Video.owner_id == user.id, Video.created_at <= end]
    sf = [Session.owner_id == user.id, Session.started_at <= end]
    if start:
        vf.append(Video.created_at >= start)
        sf.append(Session.started_at >= start)
    # Select summary JSON only, not per-frame arrays, tracks or media paths.
    videos = list(db.execute(select(Video.id, Video.created_at, Video.status,
        Video.crowd_analysis['summary'].label('summary')).where(*vf)))
    sessions = [session_row(row) for row in db.execute(session_query().where(*sf)
        .order_by(Session.started_at.desc(), Session.id))]
    video_events = list(db.scalars(select(AlertEvent).join(Video).where(*vf)))
    live_events = list(db.scalars(select(LiveAlertEvent).join(Session).where(*sf)))
    ve, le = defaultdict(list), defaultdict(list)
    for e in video_events:
        ve[e.video_id].append(e)
    for e in live_events:
        le[e.session_id].append(e)
    analyzed = [v for v in videos if v.summary is not None]
    video_metrics = aggregate([(v.summary, v.summary.get('processed_crowd_frames', 0)) for v in analyzed])
    live_metrics = aggregate([(s.summary or {}, s.processed_frame_count) for s, _ in sessions])
    levels = Counter()
    for v in analyzed:
        for item in v.summary.get('level_distribution', []):
            levels[item['level']] += item['frames']
    video_metrics['crowd_levels'] = dict(levels)
    live_metrics['maximum_crowd_levels'] = dict(Counter(s.summary['maximum_crowd_level'] for s, _ in sessions if s.summary.get('maximum_crowd_level')))
    video_metrics['risk_distribution'] = dict(Counter(operational_risk(e.severity for e in ve[v.id]) for v in analyzed))
    live_metrics['risk_distribution'] = dict(Counter(s.summary['maximum_operational_risk'] for s, _ in sessions if s.summary.get('maximum_operational_risk')))
    # One point per source/day; dates represent record creation/start, not video capture.
    days = defaultdict(lambda: {'video': [], 'live': []})
    for v in analyzed:
        days[utc(v.created_at).date().isoformat()]['video'].append((v.summary, v.summary.get('processed_crowd_frames', 0)))
    for s, _ in sessions:
        days[utc(s.started_at).date().isoformat()]['live'].append((s.summary or {}, s.processed_frame_count))
    history = [dict(date=day, video_average=aggregate(values['video'])['average_count'],
        live_average=aggregate(values['live'])['average_count'], video_peak=aggregate(values['video'])['peak_count'],
        live_peak=aggregate(values['live'])['peak_count']) for day, values in sorted(days.items())]
    zones = list(db.execute(select(MonitoringZone.id, MonitoringZone.name, MonitoringZone.video_id,
        MonitoringZone.analysis['summary'].label('summary')).join(Video).where(*vf)
        .order_by(MonitoringZone.created_at.desc(), MonitoringZone.id).limit(50)))
    return dict(range=range, generated_at=end, total_analyzed_videos=len(analyzed), total_live_sessions=len(sessions),
        video_statuses=dict(Counter(v.status.value for v in videos)),
        session_statuses=dict(Counter(s.status for s, _ in sessions)),
        alerts=breakdown(video_events+live_events), video=video_metrics, live=live_metrics,
        history=history[-90:], history_total_days=len(history),
        peak_periods={source: max((h for h in history if h[source+'_peak'] is not None),
            key=lambda h: h[source+'_peak'], default=None) for source in ('video', 'live')},
        sessions=[session_data(s, name, le[s.id]) for s, name in sessions[:30]],
        video_zones=[dict(id=str(z.id), name=z.name, video_id=str(z.video_id),
            peak_count=z.summary.get('maximum_simultaneous_tracks') if z.summary else None,
            average_count=z.summary.get('average_simultaneous_tracks') if z.summary else None) for z in zones])


@router.get('/sessions/{session_id}')
def detail(session_id: UUID, db: DatabaseSession, user: CurrentUser, response: Response):
    response.headers['Cache-Control'] = 'no-store'
    row = db.execute(session_query().where(Session.id == session_id, Session.owner_id == user.id)).first()
    if row is None:
        raise HTTPException(404, 'Session not found')
    events = list(db.scalars(select(LiveAlertEvent).where(LiveAlertEvent.session_id == session_id)
        .order_by(LiveAlertEvent.created_at.desc(), LiveAlertEvent.id)))
    session, name = session_row(row)
    result = session_data(session, name, events)
    result['alert_history'] = [dict(id=str(e.id), created_at=e.created_at, resolved_at=e.resolved_at,
        severity=e.severity, rule_type=e.rule_snapshot.get('rule_type', 'UNKNOWN'),
        rule_name=e.rule_snapshot.get('name', 'Stored rule'), zone_name=e.evidence.get('zone_name')) for e in events[:100]]
    return result
