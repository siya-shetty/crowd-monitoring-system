import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import engine, get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.models.operations import OperationalEvent, Incident
from app.models.live import Camera, LiveMonitoringSession, LiveAlertEvent
from app.models.video import Video
from app.models.alert import AlertEvent

NOW = datetime.now(timezone.utc)
INCIDENT = dict(title='Queue review', description='Operator checked the entrance queue.', occurred_at=NOW.isoformat())


def test_events_removed_from_routes_and_incident_contract(context):
    c, _, _, _ = context
    for path in ['/api/v1/events', '/api/v1/events/' + str(uuid.uuid4())]:
        for method in ['get', 'post', 'put', 'delete']:
            assert getattr(c, method)(path).status_code == 404
    schema = c.get('/openapi.json').json()
    assert not any('/events' in path for path in schema['paths'])
    assert 'event_id' not in schema['components']['schemas']['IncidentInput']['properties']
    for path in ['/api/v1/incidents', '/api/v1/incidents/export.csv']:
        assert 'event_id' not in [p['name'] for p in schema['paths'][path]['get']['parameters']]
    assert c.post('/api/v1/incidents', json=INCIDENT | {'event_id': str(uuid.uuid4())}).status_code == 422


def test_manual_incident_and_legacy_event_history_survive_edits(context):
    c, db, user, _ = context
    manual = c.post('/api/v1/incidents', json=INCIDENT)
    assert manual.status_code == 201, manual.text
    assert manual.json()['context'] == {} and 'event_id' not in manual.json()
    legacy = OperationalEvent(owner_id=user.id, name='Historical event', start_time=NOW)
    db.add(legacy); db.flush()
    snapshot = {'event': {'id': str(legacy.id), 'label': legacy.name}}
    item = Incident(owner_id=user.id, title='Historical incident', occurred_at=NOW,
                    event_id=legacy.id, context=snapshot)
    db.add(item); db.commit()
    url = '/api/v1/incidents/' + str(item.id)
    for state in ['INVESTIGATING', 'RESOLVED', 'CLOSED', 'OPEN']:
        response = c.put(url, json=INCIDENT | {'status': state})
        assert response.status_code == 200, response.text
        assert response.json()['context'] == {} and 'event_id' not in response.json()
        db.refresh(item)
        assert item.event_id == legacy.id and item.context == snapshot
    assert c.get(url).status_code == 200
    assert len(c.get('/api/v1/incidents').json()) == 2
    report = c.get('/api/v1/incidents/export.csv')
    assert report.status_code == 200 and 'Historical event' not in report.text
    assert c.delete(url).status_code == 204
    assert db.get(OperationalEvent, legacy.id) is not None


@pytest.fixture
def context():
    with engine.connect() as connection:
        transaction = connection.begin()
        with Session(connection, join_transaction_mode='create_savepoint') as db:
            owner=User(id=uuid.uuid4(), email=uuid.uuid4().hex+'@example.com', full_name='Owner', hashed_password='unused')
            other=User(id=uuid.uuid4(), email=uuid.uuid4().hex+'@example.com', full_name='Other', hashed_password='unused')
            db.add_all([owner,other]); db.commit()
            app.dependency_overrides[get_db]=lambda:db
            app.dependency_overrides[get_current_user]=lambda:owner
            try:yield TestClient(app),db,owner,other
            finally:app.dependency_overrides.clear()
        transaction.rollback()


def sources(db,user):
    camera=Camera(owner_id=user.id,name='Entrance')
    video=Video(owner_id=user.id,original_filename='fixture.mp4',storage_key=uuid.uuid4().hex,content_type='video/mp4',file_size=1)
    db.add_all([camera,video]);db.flush()
    session=LiveMonitoringSession(owner_id=user.id,camera_id=camera.id,status='STOPPED',started_at=NOW,summary={})
    db.add(session);db.flush()
    alert=AlertEvent(video_id=video.id,rule_name='Queue threshold',rule_type='CROWD_COUNT_ABOVE',severity='WARNING',configuration={},condition_start_seconds=1,trigger_seconds=3,end_seconds=4,evidence={'zone_name':'Entrance Zone'})
    live=LiveAlertEvent(session_id=session.id,rule_snapshot={'name':'Zone presence','rule_type':'ZONE_PRESENCE'},severity='CRITICAL',evidence={'zone_name':'Gate'})
    db.add_all([alert,live]);db.commit()
    return dict(camera_id=camera.id,video_id=video.id,live_session_id=session.id,alert_event_id=alert.id,live_alert_event_id=live.id)


def test_auth_empty_and_inactive(context):
    c,db,user,_=context
    assert c.get('/api/v1/incidents').json()==[]
    assert c.get('/api/v1/incidents/options').json()=={'cameras':[],'videos':[],'sessions':[]}
    assert len(list(csv.reader(io.StringIO(c.get('/api/v1/incidents/export.csv').text.lstrip('\ufeff')))))==1
    user.is_active=False;db.commit()
    assert c.get('/api/v1/incidents').status_code==403
    app.dependency_overrides.pop(get_current_user)
    for path in ['/incidents','/incidents/options','/incidents/export.csv','/incidents/alert-context?source=video&alert_id='+str(uuid.uuid4())]:
        assert c.get('/api/v1'+path).status_code==401
    assert c.post('/api/v1/incidents',json=INCIDENT).status_code==401


def test_realistic_workflow_and_export(context):
    c,db,user,_=context
    refs=sources(db,user)
    draft=c.get('/api/v1/incidents/alert-context',params={'source':'video','alert_id':str(refs['alert_event_id'])}).json()
    assert draft['occurred_at'] is None and draft['context']['video_offset_seconds']==3
    assert c.get('/api/v1/incidents').json()==[]  # Reading a draft never creates an incident.
    body=INCIDENT|{'alert_event_id':str(refs['alert_event_id']),'title':'=HYPERLINK("bad")','description':'Queue, checked\nNo identity collected.'}
    r=c.post('/api/v1/incidents',json=body);assert r.status_code==201,r.text
    item=r.json();url='/api/v1/incidents/'+item['id']
    assert item['video_id']==str(refs['video_id']) and item['context']['alert']['zone']=='Entrance Zone'
    for status in ['INVESTIGATING','RESOLVED','CLOSED','OPEN']:
        result=c.put(url,json=body|{'status':status});assert result.status_code==200,result.text
        assert bool(result.json()['resolved_at'])==(status in ['RESOLVED','CLOSED'])
    c.put(url,json=body|{'status':'RESOLVED'})
    assert c.get('/api/v1/incidents?status=OPEN').json()==[]
    assert len(c.get('/api/v1/incidents?severity=WARNING').json())==1
    report=c.get('/api/v1/incidents/export.csv?severity=WARNING')
    assert report.status_code==200 and report.headers['cache-control']=='no-store'
    assert report.headers['content-disposition']=='attachment; filename="incidents.csv"'
    rows=list(csv.DictReader(io.StringIO(report.text.lstrip('\ufeff'))))
    assert len(rows)==1 and rows[0]['title'].startswith("'=HYPERLINK")
    assert rows[0]['status']=='RESOLVED'
    assert 'event' not in rows[0] and 'event_id' not in rows[0]
    assert rows[0]['description']==body['description'] and rows[0]['alert_type']=='CROWD_COUNT_ABOVE'
    assert rows[0]['video']=='fixture.mp4' and rows[0]['video_offset_seconds']=='3.0'
    assert 'storage_key' not in report.text and 'hashed_password' not in report.text
    assert c.delete(url).status_code==204 and c.get(url).status_code==404


def test_live_alert_and_deleted_sources_preserve_context(context):
    c,db,user,_=context
    refs=sources(db,user)
    draft=c.get('/api/v1/incidents/alert-context',params={'source':'live','alert_id':str(refs['live_alert_event_id'])}).json()
    assert draft['severity']=='CRITICAL' and draft['occurred_at']
    body=INCIDENT|{'live_alert_event_id':str(refs['live_alert_event_id']),'severity':draft['severity']}
    r=c.post('/api/v1/incidents',json=body);assert r.status_code==201,r.text
    item=r.json();url='/api/v1/incidents/'+item['id']
    assert item['live_session_id']==str(refs['live_session_id']) and item['camera_id']==str(refs['camera_id'])
    db.execute(delete(Camera).where(Camera.id==refs['camera_id']));db.commit()
    db.expire_all()
    saved=c.get(url).json()
    assert saved['camera_id'] is None and saved['live_session_id'] is None and saved['live_alert_event_id'] is None
    assert saved['context']['live_alert']['label']=='Zone presence'
    updated=c.put(url,json=INCIDENT|{'status':'CLOSED'}).json()
    assert updated['context']==saved['context']  # Editing after FK deletion retains history.


@pytest.mark.parametrize('key',['camera_id','video_id','live_session_id','alert_event_id','live_alert_event_id'])
def test_cross_owner_relationships_rejected_on_create_and_update(context,key):
    c,db,user,other=context
    refs=sources(db,other)
    bad=INCIDENT|{key:str(refs[key])}
    assert c.post('/api/v1/incidents',json=bad).status_code==404
    item=c.post('/api/v1/incidents',json=INCIDENT).json()
    assert c.put('/api/v1/incidents/'+item['id'],json=bad).status_code==404
    assert c.get('/api/v1/incidents/'+item['id']).json()['context']=={}


def test_foreign_records_reports_drafts_and_options(context):
    c,db,user,other=context
    refs=sources(db,other)
    foreign=Incident(owner_id=other.id,title='Private',occurred_at=NOW,context={})
    db.add(foreign);db.commit()
    for method in ['get','put','delete']:
        kwargs={'json':INCIDENT} if method=='put' else {}
        assert getattr(c,method)('/api/v1/incidents/'+str(foreign.id),**kwargs).status_code==404
    for source,key in [('video','alert_event_id'),('live','live_alert_event_id')]:
        assert c.get('/api/v1/incidents/alert-context',params={'source':source,'alert_id':str(refs[key])}).status_code==404
    assert 'Private' not in c.get('/api/v1/incidents/export.csv').text
    assert c.get('/api/v1/incidents/options').json()=={'cameras':[],'videos':[],'sessions':[]}


def test_invalid_context_status_times_and_small_snapshot(context):
    c,db,user,_=context
    a=sources(db,user);b=sources(db,user)
    for values in [{'alert_event_id':str(a['alert_event_id']),'video_id':str(b['video_id'])},
                   {'live_session_id':str(a['live_session_id']),'camera_id':str(b['camera_id'])},
                   {'alert_event_id':str(a['alert_event_id']),'live_alert_event_id':str(a['live_alert_event_id'])},
                   {'title':' '},{'status':'DANGER'},{'severity':'HIGH'},
                   {'resolved_at':(NOW-timedelta(days=1)).isoformat()},
                   {'status':'RESOLVED','occurred_at':(NOW+timedelta(days=1)).isoformat()},
                   {'context':{'secret':'forged'}}]:
        assert c.post('/api/v1/incidents',json=INCIDENT|values).status_code==422
    r=c.post('/api/v1/incidents',json=INCIDENT|{'video_id':str(a['video_id'])});item=r.json()
    assert item['context']=={'video':{'id':str(a['video_id']),'label':'fixture.mp4'}}
    assert c.put('/api/v1/incidents/'+item['id'],json=INCIDENT).json()['context']=={}
