from uuid import UUID
import asyncio
import time
from fastapi import APIRouter, HTTPException, Request, Query
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from app.api.v1.dependencies import DatabaseSession
from app.api.v1.videos import CurrentUser
from app.core.config import get_settings
from app.models.live import Camera, CameraZone, CameraRule, LiveMonitoringSession, LiveAlertEvent, ACTIVE
from app.schemas.live import CameraCreate, CameraUpdate, CameraResponse, CameraZoneResponse, CameraRuleCreate, CameraRuleResponse, SessionResponse
from app.schemas.spatial import ZoneCreate, ZoneUpdate
from app.services import live

router = APIRouter(tags=['live'])


def camera_for(db, user, camera_id, lock=False):
    query = select(Camera).where(Camera.id == camera_id, Camera.owner_id == user.id)
    camera = db.scalar(query.with_for_update() if lock else query)
    if camera is None:
        raise HTTPException(404, 'Camera not found')
    return camera


def session_for(db, user, session_id):
    session = db.scalar(select(LiveMonitoringSession).where(LiveMonitoringSession.id == session_id, LiveMonitoringSession.owner_id == user.id))
    if session is None:
        raise HTTPException(404, 'Session not found')
    return session


def child_for(db, model, camera_id, item_id):
    item = db.scalar(select(model).where(model.camera_id == camera_id, model.id == item_id))
    if item is None:
        raise HTTPException(404, 'Camera configuration not found')
    return item


@router.get('/live/config')
def config(user: CurrentUser):
    s = get_settings()
    return dict(target_fps=s.live_target_fps, max_frame_bytes=s.live_max_frame_bytes,
                capture_width=960, capture_height=540, stale_seconds=s.live_session_stale_seconds)


@router.post('/cameras', response_model=CameraResponse, status_code=201)
def create_camera(payload: CameraCreate, db: DatabaseSession, user: CurrentUser):
    camera = Camera(owner_id=user.id, **payload.model_dump())
    db.add(camera)
    db.commit()
    return camera


@router.get('/cameras', response_model=list[CameraResponse])
def cameras(db: DatabaseSession, user: CurrentUser):
    return list(db.scalars(select(Camera).where(Camera.owner_id == user.id).order_by(Camera.created_at).limit(200)))


@router.get('/cameras/{camera_id}', response_model=CameraResponse)
def camera(camera_id: UUID, db: DatabaseSession, user: CurrentUser):
    return camera_for(db, user, camera_id)


@router.patch('/cameras/{camera_id}', response_model=CameraResponse)
def edit_camera(camera_id: UUID, payload: CameraUpdate, db: DatabaseSession, user: CurrentUser):
    item = camera_for(db, user, camera_id, True)
    for key,value in payload.model_dump(exclude_unset=True).items():
        setattr(item,key,value)
    db.commit()
    return item


@router.delete('/cameras/{camera_id}', status_code=204)
def delete_camera(camera_id: UUID, db: DatabaseSession, user: CurrentUser):
    item = camera_for(db,user,camera_id,True)
    if db.scalar(select(LiveMonitoringSession.id).where(LiveMonitoringSession.camera_id == camera_id, LiveMonitoringSession.status.in_(ACTIVE)).limit(1)):
        raise HTTPException(409,'Stop monitoring before deleting the camera')
    db.execute(delete(CameraRule).where(CameraRule.camera_id == camera_id))
    db.delete(item)
    db.commit()


@router.get('/cameras/{camera_id}/zones', response_model=list[CameraZoneResponse])
def zones(camera_id: UUID, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id)
    return list(db.scalars(select(CameraZone).where(CameraZone.camera_id == camera_id)))


@router.post('/cameras/{camera_id}/zones', response_model=CameraZoneResponse, status_code=201)
def create_zone(camera_id: UUID, payload: ZoneCreate, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id,True)
    if db.scalar(select(func.count()).select_from(CameraZone).where(CameraZone.camera_id == camera_id)) >= 50:
        raise HTTPException(409,'At most 50 zones per camera')
    item = CameraZone(camera_id=camera_id, **payload.model_dump(mode='json'))
    db.add(item)
    db.commit()
    return item


@router.patch('/cameras/{camera_id}/zones/{zone_id}', response_model=CameraZoneResponse)
def edit_zone(camera_id: UUID, zone_id: UUID, payload: ZoneUpdate, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id,True)
    item = child_for(db,CameraZone,camera_id,zone_id)
    for key,value in payload.model_dump(mode='json',exclude_unset=True).items():
        setattr(item,key,value)
    db.commit()
    return item


@router.delete('/cameras/{camera_id}/zones/{zone_id}', status_code=204)
def delete_zone(camera_id: UUID, zone_id: UUID, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id,True)
    item = child_for(db,CameraZone,camera_id,zone_id)
    if db.scalar(select(CameraRule.id).where(CameraRule.zone_id == zone_id).limit(1)):
        raise HTTPException(409,'Delete referencing camera rules first')
    db.delete(item)
    db.commit()


@router.get('/cameras/{camera_id}/alert-rules', response_model=list[CameraRuleResponse])
def rules(camera_id: UUID, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id)
    return list(db.scalars(select(CameraRule).where(CameraRule.camera_id == camera_id)))


@router.post('/cameras/{camera_id}/alert-rules', response_model=CameraRuleResponse, status_code=201)
def create_rule(camera_id: UUID, payload: CameraRuleCreate, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id,True)
    if payload.zone_id:
        child_for(db,CameraZone,camera_id,payload.zone_id)
    if db.scalar(select(func.count()).select_from(CameraRule).where(CameraRule.camera_id == camera_id)) >= 50:
        raise HTTPException(409,'At most 50 rules per camera')
    item = CameraRule(camera_id=camera_id, **payload.model_dump())
    db.add(item)
    db.commit()
    return item


@router.put('/cameras/{camera_id}/alert-rules/{rule_id}', response_model=CameraRuleResponse)
def edit_rule(camera_id: UUID, rule_id: UUID, payload: CameraRuleCreate, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id,True)
    item = child_for(db,CameraRule,camera_id,rule_id)
    if payload.zone_id:
        child_for(db,CameraZone,camera_id,payload.zone_id)
    for key,value in payload.model_dump().items():
        setattr(item,key,value)
    db.commit()
    return item


@router.delete('/cameras/{camera_id}/alert-rules/{rule_id}', status_code=204)
def delete_rule(camera_id: UUID, rule_id: UUID, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id,True)
    db.delete(child_for(db,CameraRule,camera_id,rule_id))
    db.commit()


@router.post('/cameras/{camera_id}/sessions', status_code=201, response_model=SessionResponse)
def start(camera_id: UUID, db: DatabaseSession, user: CurrentUser):
    item = camera_for(db,user,camera_id,True)
    if not item.enabled:
        raise HTTPException(409,'Camera is disabled')
    if db.scalar(select(LiveMonitoringSession.id).where(LiveMonitoringSession.camera_id == camera_id, LiveMonitoringSession.status.in_(ACTIVE)).limit(1)):
        raise HTTPException(409,'Camera already has an active session')
    with live.registry:
        if len(live.runtime) >= get_settings().live_max_sessions:
            raise HTTPException(503,'Live session capacity reached')
        session = LiveMonitoringSession(camera_id=camera_id,owner_id=user.id)
        db.add(session)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409,'Camera already has an active session') from None
        z = [CameraZoneResponse.model_validate(z).model_dump(mode='json') for z in db.scalars(select(CameraZone).where(CameraZone.camera_id == camera_id))]
        r = [CameraRuleResponse.model_validate(r).model_dump(mode='json') for r in db.scalars(select(CameraRule).where(CameraRule.camera_id == camera_id))]
        session.summary = {'zones':z, 'rules':r}
        state = live.SessionState(z,r)
        state.lock.acquire()
        live.runtime[session.id] = state
        db.commit()
    try:
        live.cv(session.id,'start')
        session.status = 'RUNNING'
        db.commit()
    except HTTPException:
        live.finish(db,session,'worker_start_failed',failed=True)
        raise
    finally:
        state.lock.release()
    return session


@router.get('/cameras/{camera_id}/sessions', response_model=list[SessionResponse])
def history(camera_id: UUID, db: DatabaseSession, user: CurrentUser):
    camera_for(db,user,camera_id)
    return list(db.scalars(select(LiveMonitoringSession).where(LiveMonitoringSession.camera_id == camera_id).order_by(LiveMonitoringSession.created_at.desc()).limit(100)))


@router.get('/live/sessions/{session_id}')
def snapshot(session_id: UUID, db: DatabaseSession, user: CurrentUser):
    session = session_for(db,user,session_id)
    state = live.runtime.get(session_id)
    last = session.last_frame_at or session.started_at
    stale = session.status in ACTIVE and (live.now()-last).total_seconds() > get_settings().live_session_stale_seconds
    result = {c.name:getattr(session,c.name) for c in session.__table__.columns if c.name != 'owner_id'}
    result.update(is_stale=stale, recent_observations=list(state.recent) if state else [])
    return result


@router.get('/live/sessions/{session_id}/alerts')
def events(session_id: UUID, db: DatabaseSession, user: CurrentUser, offset: int = Query(default=0,ge=0)):
    session_for(db,user,session_id)
    return list(db.scalars(select(LiveAlertEvent).where(LiveAlertEvent.session_id == session_id).order_by(LiveAlertEvent.created_at,LiveAlertEvent.id).offset(offset).limit(100)))


def drop(db, session_id):
    db.execute(update(LiveMonitoringSession).where(LiveMonitoringSession.id == session_id).values(dropped_frame_count=LiveMonitoringSession.dropped_frame_count+1))
    db.commit()


@router.post('/live/sessions/{session_id}/frames')
async def frames(session_id: UUID, request: Request, db: DatabaseSession, user: CurrentUser,
                 sequence: int = Query(ge=1), capture_timestamp: float = Query(ge=0,allow_inf_nan=False)):
    session = session_for(db,user,session_id)
    if session.status != 'RUNNING':
        raise HTTPException(409,'Session is not running')
    state = live.runtime.get(session_id)
    if state is None:
        live.finish(db,session,'backend_state_lost',failed=True)
        raise HTTPException(410,'Session state lost; start a new session')
    content_type = request.headers.get('content-type','').split(';')[0]
    if content_type not in ('image/jpeg','image/webp'):
        raise HTTPException(415,'Use binary JPEG or WebP')
    if not state.lock.acquire(False):
        await run_in_threadpool(drop,db,session_id)
        raise HTTPException(429,'Frame dropped: session busy')
    try:
        db.refresh(session)
        if session.status != 'RUNNING' or live.runtime.get(session_id) is not state:
            raise HTTPException(409,'Session is not running')
        if sequence <= state.sequence or capture_timestamp <= state.capture:
            raise HTTPException(409,'Frame sequence and capture timestamp must advance')
        if abs(time.time()-capture_timestamp) > 60:
            raise HTTPException(422,'Capture timestamp must be within 60 seconds of server time')
        if state.last_accept is not None and time.monotonic()-state.last_accept < 1/get_settings().live_target_fps:
            await run_in_threadpool(drop,db,session_id)
            raise HTTPException(429,'Frame dropped: target ingestion rate exceeded')
        data = bytearray()
        try:
            async with asyncio.timeout(10):
                async for chunk in request.stream():
                    if len(data)+len(chunk) > get_settings().live_max_frame_bytes:
                        raise HTTPException(413,'Frame exceeds byte limit')
                    data.extend(chunk)
        except TimeoutError:
            raise HTTPException(408,'Frame upload timed out') from None
        if not data:
            raise HTTPException(422,'Empty frame')
        received = live.now()
        try:
            return await run_in_threadpool(live.process,db,session,state,bytes(data),sequence,capture_timestamp,content_type,received)
        except HTTPException as error:
            if error.status_code == 429:
                await run_in_threadpool(drop,db,session_id)
            raise
        except Exception:
            db.rollback()
            try:
                await run_in_threadpool(live.cv,session_id,'stop')
            except HTTPException:
                pass
            await run_in_threadpool(live.finish,db,session,'snapshot_persistence_failed',True)
            raise HTTPException(503,'Live session interrupted') from None
    finally:
        state.lock.release()


@router.post('/live/sessions/{session_id}/stop', response_model=SessionResponse)
def stop(session_id: UUID, db: DatabaseSession, user: CurrentUser):
    session = session_for(db,user,session_id)
    state = live.runtime.get(session_id)
    if state:
        state.lock.acquire()
    try:
        db.refresh(session)
        if session.status not in ACTIVE:
            return session
        session.status = 'STOPPING'
        db.commit()
        try:
            live.cv(session_id,'stop')
        except HTTPException:
            live.finish(db,session,'worker_unavailable_on_stop',failed=True)
        else:
            live.finish(db,session)
        return session
    finally:
        if state:
            state.lock.release()


@router.delete('/live/sessions/{session_id}', status_code=204)
def delete_session(session_id: UUID, db: DatabaseSession, user: CurrentUser):
    session = session_for(db,user,session_id)
    if session.status in ACTIVE:
        raise HTTPException(409,'Stop session before deleting its history')
    db.delete(session)
    db.commit()
