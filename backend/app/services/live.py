"""Single backend-process coordinator; the CV worker owns all tracker state."""
import time
from functools import lru_cache
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from types import SimpleNamespace
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.models.live import LiveMonitoringSession, LiveAlertEvent, ACTIVE
from app.schemas.live import FrameObservation
from app.schemas.spatial import Point
from app.services.spatial_geometry import foot_point, contains
from app.services.live_alerts import LiveRuleState
from app.services.alert_engine import operational_risk

runtime = {}
registry = Lock()


def now():
    return datetime.now(timezone.utc)


@lru_cache(maxsize=1)
def cv_client():
    # Reuse connections and avoid environment-proxy setup on every camera frame.
    return httpx.Client(timeout=30, trust_env=False)


def cv(session_id, action, **kwargs):
    try:
        response = cv_client().post(f'{get_settings().cv_service_url}/live/sessions/{session_id}/{action}', **kwargs)
        if response.status_code >= 400:
            status = response.status_code if response.status_code in (409, 410, 413, 415, 422, 429) else 503
            raise HTTPException(status, {409:'Frame sequence must advance',410:'Live worker state lost; start a new session',
                413:'Frame exceeds byte limit',415:'Unsupported frame format',422:'Invalid frame or dimensions',
                429:'Frame dropped: worker busy',503:'Live processing unavailable'}[status])
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(503, 'Live processing unavailable') from None


class SessionState:
    def __init__(self, zones, rules):
        self.lock = Lock()
        self.origin = time.monotonic()
        self.last_accept = None
        self.sequence = 0
        self.capture = -1
        self.recent = deque(maxlen=get_settings().live_recent_observations)
        self.zones = zones
        self.rules = [LiveRuleState(r) for r in rules]


def close_events(db, session, reason):
    for event in db.scalars(select(LiveAlertEvent).where(LiveAlertEvent.session_id == session.id, LiveAlertEvent.resolved_at.is_(None))):
        event.evidence = event.evidence | {'closure': reason}
        event.resolved_at = now()


def finish(db, session, reason='session_stopped', failed=False):
    session.status = 'FAILED' if failed else 'STOPPED'
    session.stopped_at = now()
    if failed:
        session.error_summary = reason
    close_events(db, session, reason)
    summary = dict(session.summary)
    summary.update(duration_seconds=max(0, (session.stopped_at-session.started_at).total_seconds()),
        processed_frames=session.processed_frame_count, dropped_frames=session.dropped_frame_count,
        closure=reason)
    session.summary = summary
    if session.latest_snapshot:
        session.latest_snapshot = session.latest_snapshot | {'current_operational_risk':'NORMAL', 'active_alert_count':0}
    with registry:
        runtime.pop(session.id, None)
    db.commit()


def reconcile(db):
    for session in list(db.scalars(select(LiveMonitoringSession).where(LiveMonitoringSession.status.in_(ACTIVE)))):
        try:
            cv(session.id, 'stop')
        except HTTPException:
            pass  # CV idle expiry also releases unreachable orphan workers.
        finish(db, session, 'backend_restarted', failed=True)


def process(db, session, state, data, sequence, capture, content_type, received):
    try:
        raw = cv(session.id, 'frame', content=data, headers={'Content-Type':content_type},
            params={'sequence':sequence, 'capture_timestamp':capture})
        observation = FrameObservation.model_validate(raw).model_dump()
        if observation['sequence'] != sequence or observation['capture_timestamp'] != capture:
            raise ValueError('Mismatched worker response')
    except HTTPException as error:
        if error.status_code in (410, 503):
            try:
                cv(session.id, 'stop')
            except HTTPException:
                pass
            finish(db, session, 'worker_unavailable', failed=True)
        raise
    except Exception:
        try:
            cv(session.id, 'stop')
        except HTTPException:
            pass
        finish(db, session, 'invalid_worker_response', failed=True)
        raise HTTPException(503, 'Live worker response invalid') from None
    timestamp = time.monotonic()-state.origin
    observation.update(session_id=str(session.id), timestamp_seconds=timestamp,
        received_at=received.isoformat(), processed_at=now().isoformat(), zones={})
    points = [(t['track_id'], foot_point(SimpleNamespace(**t), observation['width'], observation['height'])) for t in observation['tracks']]
    for zone in state.zones:
        if zone['active']:
            polygon = [Point(**p) for p in zone['polygon']]
            ids = sorted(i for i,p in points if p and contains(polygon, Point(x=p[0],y=p[1])))
            observation['zones'][zone['id']] = dict(name=zone['name'], active_tracks_in_zone=len(ids), track_ids_in_zone=ids)
    triggered, resolved = [], []
    for rule in state.rules:
        for event_id, evidence in rule.step(timestamp, observation, state.recent):
            event = db.get(LiveAlertEvent, event_id)
            event.evidence, event.resolved_at = evidence, now()
            resolved.append(str(event.id))
        if rule.trigger is not None:
            if rule.event_id is None:
                event = LiveAlertEvent(session_id=session.id, rule_snapshot=rule.rule,
                    severity=rule.rule['severity'], evidence=rule.evidence())
                db.add(event)
                db.flush()
                rule.event_id = event.id
                triggered.append(str(event.id))
            else:
                db.get(LiveAlertEvent, rule.event_id).evidence = rule.evidence()
    active = [r.rule['severity'] for r in state.rules if r.trigger is not None]
    risk = operational_risk(active)
    observation.update(current_operational_risk=risk, active_alert_count=len(active),
        triggered_alert_ids=triggered, resolved_alert_ids=resolved)
    session.processed_frame_count += 1
    session.last_frame_at = received
    session.latest_snapshot = observation
    summary = dict(session.summary)
    count = observation['observed_crowd_count']
    n = session.processed_frame_count
    summary['maximum_observed_crowd_count'] = max(summary.get('maximum_observed_crowd_count',0), count)
    summary['average_observed_crowd_count'] = summary.get('average_observed_crowd_count',0)+(count-summary.get('average_observed_crowd_count',0))/n
    duration = observation['processing_duration_seconds']
    summary['average_processing_duration_seconds'] = summary.get('average_processing_duration_seconds',0)+(duration-summary.get('average_processing_duration_seconds',0))/n
    for key, value, order in [('maximum_crowd_level',observation['crowd_level'],('LOW','MODERATE','HIGH','VERY_HIGH')),
                             ('maximum_operational_risk',risk,('NORMAL','ELEVATED','HIGH','CRITICAL'))]:
        summary[key] = max((summary.get(key,order[0]),value),key=order.index)
    summary['alert_event_count'] = summary.get('alert_event_count',0)+len(triggered)
    peaks = dict(summary.get('zone_peak_counts',{}))
    for key, zone in observation['zones'].items():
        peaks[key] = max(peaks.get(key,0),zone['active_tracks_in_zone'])
    summary['zone_peak_counts'] = peaks
    session.summary = summary
    db.commit()
    state.sequence, state.capture, state.last_accept = sequence, capture, time.monotonic()
    # Retain aggregate observations only, never per-frame tracks or image bytes.
    state.recent.append({k:observation[k] for k in ('timestamp_seconds','observed_crowd_count','crowd_level')})
    return observation
