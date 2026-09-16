import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.db.session import SessionLocal
from app.models.alert import AlertRule, AlertEvent
from test_videos import register_and_login
from test_tracking import payload, mock_cv


def test_alert_lifecycle_ownership_and_no_inference(monkeypatch):
    mock_cv(monkeypatch,payload())
    client=TestClient(app); owner=register_and_login(); other=register_and_login()
    video=client.post('/api/v1/videos',headers=owner,files={'file':('alerts.mp4',b'test','video/mp4')}).json()
    base='/api/v1/videos/'+video['id'];url=base+'/alert-rules'
    def forbidden(*a,**kw):raise AssertionError('Alert changes must not call CV')
    monkeypatch.setattr('app.api.v1.videos.analyze_video',forbidden)
    monkeypatch.setattr('app.services.video_processing.httpx.post',forbidden)
    body=dict(name='Count',rule_type='CROWD_COUNT_ABOVE',scope='VIDEO',severity='INFO',configuration={'threshold':1})
    for headers,code in [({},401),(other,404)]:
        for suffix in ['/alert-rules','/alerts','/alert-summary']:
            assert client.get(base+suffix,headers=headers).status_code==code
        assert client.post(url,headers=headers,json=body).status_code==code
    response=client.post(url,headers=owner,json=body);assert response.status_code==201,response.text
    import json
    for invalid in (float('nan'),float('inf'),float('-inf')):
        malformed=body | {'configuration':{'threshold':1,'minimum_duration_seconds':invalid}}
        assert client.post(url,headers=owner | {'Content-Type':'application/json'},content=json.dumps(malformed)).status_code==422
    rule=response.json();detail=url+'/'+rule['id']
    events=lambda:client.get(base+'/alerts',headers=owner).json()
    summary=lambda:client.get(base+'/alert-summary',headers=owner).json()
    assert len(events())==1 and summary()['maximum_operational_risk']=='ELEVATED'
    first=events()[0]
    assert client.get(base+'/alerts/'+first['id'],headers=other).status_code==404
    assert client.get('/api/v1/alerts',headers={}).status_code==401
    assert not any(e['video_id']==video['id'] for e in client.get('/api/v1/alerts',headers=other).json())
    for method in ('get','patch','delete'):
        kwargs={'json':{'name':'stolen'}} if method=='patch' else {}
        assert getattr(client,method)(detail,headers=other,**kwargs).status_code==404
    assert client.patch(detail,headers=owner,json={'configuration':{'threshold':999}}).status_code==200
    assert events()==[]
    for config,expected in [({'threshold':1,'minimum_duration_seconds':2},0),({'threshold':1,'minimum_duration_seconds':0},1)]:
        assert client.patch(detail,headers=owner,json={'configuration':config}).status_code==200
        assert len(events())==expected
    for sev,risk in [('WARNING','HIGH'),('CRITICAL','CRITICAL')]:
        assert client.patch(detail,headers=owner,json={'severity':sev}).status_code==200
        assert summary()['maximum_operational_risk']==risk
    assert client.patch(detail,headers=owner,json={'name':'Renamed'}).status_code==200
    assert events()[0]['rule_name']=='Renamed'
    for enabled in [False,True]:
        assert client.patch(detail,headers=owner,json={'enabled':enabled}).status_code==200
        assert len(events())==1
    evidence=events()[0]['evidence']
    for _ in range(2):
        assert client.post(detail+'/evaluate',headers=owner).status_code==200
        assert len(events())==1 and events()[0]['evidence']==evidence
    for invalid in [{'configuration':{'threshold':0}},{'enabled':None},{'unknown':1},{'scope':'ZONE'},{'zone_id':str(uuid.uuid4())}]:
        assert client.patch(detail,headers=owner,json=invalid).status_code==422
    square=[{'x':x,'y':y} for x,y in [(0,0),(1,0),(1,1),(0,1)]]
    z=client.post(base+'/zones',headers=owner,json={'name':'Path','polygon':square}).json()
    zonebody=dict(name='Presence',scope='ZONE',zone_id=z['id'],rule_type='ZONE_PRESENCE',configuration={})
    zr=client.post(url,headers=owner,json=zonebody);assert zr.status_code==201,zr.text
    zid=zr.json()['id']
    assert len(events())==2
    assert client.delete(base+'/zones/'+z['id'],headers=owner).status_code==409
    assert client.patch(base+'/zones/'+z['id'],headers=owner,json={'active':False}).status_code==200
    assert len(events())==1
    assert client.patch(base+'/zones/'+z['id'],headers=owner,json={'active':True}).status_code==200
    assert len(events())==2
    assert client.delete(url+'/'+zid,headers=owner).status_code==204
    assert client.delete(base+'/zones/'+z['id'],headers=owner).status_code==204
    assert len(events())==2 and any(e['rule_id'] is None and e['evidence']['zone_name']=='Path' for e in events())
    assert client.get(base,headers=owner).json()['crowd_analysis']==video['crowd_analysis']
    # Also delete a video with live zone-rule dependencies, not just orphaned history.
    remaining_zone=client.post(base+'/zones',headers=owner,json={'name':'Remaining','polygon':square}).json()
    zonebody['zone_id']=remaining_zone['id']
    assert client.post(url,headers=owner,json=zonebody).status_code==201
    assert client.delete(base,headers=owner).status_code==204
    with SessionLocal() as db:
        assert list(db.scalars(select(AlertRule).where(AlertRule.video_id==uuid.UUID(video['id']))))==[]
        assert list(db.scalars(select(AlertEvent).where(AlertEvent.video_id==uuid.UUID(video['id']))))==[]


def test_foreign_zone_and_concurrent_evaluation(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    mock_cv(monkeypatch,payload())
    client=TestClient(app);owner=register_and_login();other=register_and_login()
    def upload(headers):return client.post('/api/v1/videos',headers=headers,files={'file':('concurrency.mp4',b'test','video/mp4')}).json()['id']
    first=upload(owner);second=upload(other)
    zone=client.post(f'/api/v1/videos/{second}/zones',headers=other,json={'name':'Foreign','polygon':[{'x':0,'y':0},{'x':1,'y':0},{'x':1,'y':1},{'x':0,'y':1}]}).json()
    base=f'/api/v1/videos/{first}'
    body={'name':'Foreign','scope':'ZONE','rule_type':'ZONE_PRESENCE','zone_id':zone['id'],'configuration':{}}
    assert client.post(base+'/alert-rules',headers=owner,json=body).status_code==404
    r=client.post(base+'/alert-rules',headers=owner,json={'name':'Concurrent','scope':'VIDEO','rule_type':'CROWD_COUNT_ABOVE','configuration':{'threshold':1}}).json()
    def evaluate(_):
        with TestClient(app) as session:return session.post(base+'/alert-rules/'+r['id']+'/evaluate',headers=owner).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:assert list(pool.map(evaluate,range(2)))==[200,200]
    assert len(client.get(base+'/alerts',headers=owner).json())==1
    assert client.delete(base,headers=owner).status_code==204
    assert client.delete(f'/api/v1/videos/{second}',headers=other).status_code==204
