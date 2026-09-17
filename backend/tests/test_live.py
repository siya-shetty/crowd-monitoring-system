import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.services import live
from app.models.live import LiveMonitoringSession, LiveAlertEvent
from app.db.session import SessionLocal
from test_videos import register_and_login


def fake_cv(id,action,**kwargs):
    if action != 'frame':return {'status':'RUNNING' if action=='start' else 'STOPPED'}
    params=kwargs['params']
    return dict(sequence=params['sequence'],capture_timestamp=params['capture_timestamp'],width=64,height=64,
        tracks=[dict(track_id=1,x1=1,y1=1,x2=30,y2=50,confidence=.9)],observed_crowd_count=1,
        image_occupancy_ratio=.2,crowd_concentration=0.,crowd_level='LOW',crowd_count_delta=0,
        crowd_trend='stable',processing_duration_seconds=.1)


def setup(monkeypatch):
    monkeypatch.setattr(live,'cv',fake_cv)
    client=TestClient(app);owner=register_and_login();other=register_and_login()
    camera=client.post('/api/v1/cameras',headers=owner,json={'name':'Live test'}).json()
    return client,owner,other,'/api/v1/cameras/'+camera['id']


def send(client,url,owner,seq=1):
    return client.post(url+'/frames',headers=owner|{'Content-Type':'image/jpeg'},params={'sequence':seq,'capture_timestamp':time.time()},content=b'frame')


def test_camera_session_ownership_zones_rules_summary_and_deletion(monkeypatch):
    c,owner,other,base=setup(monkeypatch)
    for headers,code in (({},401),(other,404)):
        for suffix in ('','/zones','/alert-rules','/sessions'):
            assert c.get(base+suffix,headers=headers).status_code==code
        assert c.post(base+'/sessions',headers=headers).status_code==code
        assert c.delete(base,headers=headers).status_code==code
    zone=c.post(base+'/zones',headers=owner,json={'name':'Active','polygon':[{'x':0,'y':0},{'x':1,'y':0},{'x':1,'y':1},{'x':0,'y':1}]}).json()
    body=dict(name='Present',rule_type='ZONE_PRESENCE',scope='ZONE',zone_id=zone['id'],configuration={},severity='CRITICAL')
    rule=c.post(base+'/alert-rules',headers=owner,json=body);assert rule.status_code==201,rule.text
    response=c.post(base+'/sessions',headers=owner);assert response.status_code==201,response.text
    id=response.json()['id'];url='/api/v1/live/sessions/'+id
    assert c.post(base+'/sessions',headers=owner).status_code==409
    assert c.delete(base,headers=owner).status_code==409
    for headers,code in (({},401),(other,404)):
        assert c.get(url,headers=headers).status_code==code
        assert send(c,url,headers).status_code==code
        assert c.post(url+'/stop',headers=headers).status_code==code
        assert c.get(url+'/alerts',headers=headers).status_code==code
        assert c.post(base+'/zones',headers=headers,json={'name':'X','polygon':zone['polygon']}).status_code==code
        assert c.post(base+'/alert-rules',headers=headers,json=body).status_code==code
    frame=send(c,url,owner);assert frame.status_code==200,frame.text
    assert frame.json()['zones'][zone['id']]['active_tracks_in_zone']==1
    assert frame.json()['current_operational_risk']=='CRITICAL'
    assert send(c,url,owner).status_code==409
    assert send(c,url,owner,2).status_code==429
    snapshot=c.get(url,headers=owner).json()
    assert snapshot['processed_frame_count']==1 and snapshot['dropped_frame_count']==1
    assert snapshot['summary']['maximum_observed_crowd_count']==1
    assert c.delete(url,headers=owner).status_code==409
    for _ in range(2):assert c.post(url+'/stop',headers=owner).json()['status']=='STOPPED'
    assert uuid.UUID(id) not in live.runtime
    assert send(c,url,owner,3).status_code==409
    events=c.get(url+'/alerts',headers=owner).json()
    assert len(events)==1 and events[0]['evidence']['closure']=='session_stopped' and events[0]['resolved_at']
    assert c.delete(base+'/zones/'+zone['id'],headers=owner).status_code==409
    assert c.delete(base+'/alert-rules/'+rule.json()['id'],headers=owner).status_code==204
    assert c.delete(base+'/zones/'+zone['id'],headers=owner).status_code==204
    assert len(c.get(url+'/alerts',headers=owner).json())==1
    assert c.delete(base,headers=owner).status_code==204
    assert c.get(url,headers=owner).status_code==404


def test_concurrent_start_and_busy_drop(monkeypatch):
    c,owner,other,base=setup(monkeypatch)
    with ThreadPoolExecutor() as pool:
        results=list(pool.map(lambda _:c.post(base+'/sessions',headers=owner),range(2)))
    assert sorted(r.status_code for r in results)==[201,409]
    id=next(r.json()['id'] for r in results if r.status_code==201);url='/api/v1/live/sessions/'+id
    entered,release=Event(),Event()
    def slow(*a,**kw):
        if a[1]=='frame':entered.set();assert release.wait(10)
        return fake_cv(*a,**kw)
    monkeypatch.setattr(live,'cv',slow)
    with ThreadPoolExecutor() as pool:
        pending=pool.submit(send,c,url,owner)
        assert entered.wait(5)
        assert send(c,url,owner,2).status_code==429
        release.set();assert pending.result().status_code==200
    assert c.get(url,headers=owner).json()['dropped_frame_count']==1
    assert c.post(url+'/stop',headers=owner).status_code==200
    c.delete(base,headers=owner)


def test_validation_disabled_stale_failure_and_restart(monkeypatch):
    c,owner,_,base=setup(monkeypatch)
    assert c.patch(base,headers=owner,json={'enabled':False}).status_code==200
    assert c.post(base+'/sessions',headers=owner).status_code==409
    c.patch(base,headers=owner,json={'enabled':True})
    id=c.post(base+'/sessions',headers=owner).json()['id'];url='/api/v1/live/sessions/'+id
    assert c.post(url+'/frames',headers=owner,params={'sequence':1,'capture_timestamp':time.time()},content=b'x').status_code==415
    assert c.post(url+'/frames',headers=owner|{'Content-Type':'image/jpeg'},params={'sequence':1,'capture_timestamp':0},content=b'x').status_code==422
    assert c.post(url+'/frames',headers=owner|{'Content-Type':'image/jpeg'},params={'sequence':1,'capture_timestamp':time.time()},content=b'x'*524289).status_code==413
    with SessionLocal() as db:
        session=db.get(LiveMonitoringSession,uuid.UUID(id))
        from datetime import timedelta
        session.started_at=live.now()-timedelta(seconds=30);db.commit()
    assert c.get(url,headers=owner).json()['is_stale']
    with SessionLocal() as db:live.reconcile(db)
    assert c.get(url,headers=owner).json()['status']=='FAILED'
    assert c.get(url,headers=owner).json()['error_summary']=='backend_restarted'
    c.delete(base,headers=owner)
