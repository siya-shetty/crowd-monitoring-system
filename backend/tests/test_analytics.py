import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.api.v1.dependencies import get_current_user
from app.models.user import User
from app.models.video import Video, VideoStatus
from app.models.live import Camera, LiveMonitoringSession, LiveAlertEvent
from app.models.alert import AlertEvent
from app.models.zone import MonitoringZone


@pytest.fixture
def context():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        owner = User(id=uuid.uuid4(), email='analytics@example.com', full_name='Analytics', hashed_password='unused', role='viewer', is_active=True)
        other = User(id=uuid.uuid4(), email='other@example.com', full_name='Other', hashed_password='unused', role='viewer', is_active=True)
        db.add_all([owner, other]); db.commit()
        app.dependency_overrides[get_db] = lambda: db
        app.dependency_overrides[get_current_user] = lambda: owner
        try:
            yield TestClient(app), db, owner, other
        finally:
            app.dependency_overrides.clear()
    engine.dispose()


def populate(db, owner, days=1, count=4, frames=2):
    when = datetime.now(timezone.utc)-timedelta(days=days)
    camera = Camera(owner_id=owner.id, name='Entrance')
    db.add(camera); db.flush()
    session = LiveMonitoringSession(owner_id=owner.id, camera_id=camera.id, status='STOPPED',
        started_at=when, stopped_at=when+timedelta(minutes=18), processed_frame_count=frames, dropped_frame_count=1,
        summary={'average_observed_crowd_count':count, 'maximum_observed_crowd_count':count+2,
                 'maximum_crowd_level':'MODERATE', 'maximum_operational_risk':'HIGH',
                 'zones':[{'id':'entry','name':'Entrance Zone'}], 'zone_peak_counts':{'entry':3}},
        latest_snapshot={'current_operational_risk':'NORMAL','tracks':[{'track_id':999}]})
    video = Video(owner_id=owner.id, original_filename='fixture.mp4', storage_key=uuid.uuid4().hex,
        content_type='video/mp4', file_size=1, status=VideoStatus.COMPLETED, created_at=when,
        crowd_analysis={'summary':{'processed_crowd_frames':frames, 'average_observed_crowd_count':count,
            'maximum_observed_crowd_count':count+1, 'average_image_occupancy':.25,
            'average_crowd_concentration':.5, 'level_distribution':[{'level':'LOW','frames':frames}]}})
    db.add_all([session,video]); db.flush()
    db.add(LiveAlertEvent(session_id=session.id,severity='WARNING',rule_snapshot={'name':'Count','rule_type':'ZONE_COUNT_ABOVE'},evidence={'zone_name':'Entrance Zone'},created_at=when))
    db.add(AlertEvent(video_id=video.id,rule_name='Count',rule_type='CROWD_COUNT_ABOVE',severity='CRITICAL',configuration={},condition_start_seconds=0,trigger_seconds=1,end_seconds=2,evidence={}))
    db.add(MonitoringZone(video_id=video.id,name='Video Zone',polygon=[],analysis={'summary':{'maximum_simultaneous_tracks':3,'average_simultaneous_tracks':2}}))
    db.commit()
    return session


def test_authentication(context):
    c,db,owner,other=context
    app.dependency_overrides.pop(get_current_user)
    assert c.get('/api/v1/analytics').status_code == 401
    assert c.get('/api/v1/analytics/sessions/'+str(uuid.uuid4())).status_code == 401


def test_empty_and_validation(context):
    c,db,owner,other=context
    r=c.get('/api/v1/analytics'); assert r.status_code==200
    data=r.json()
    assert data['total_analyzed_videos']==data['total_live_sessions']==data['alerts']['total']==0
    assert data['video']['average_count'] is None and data['live']['peak_count'] is None
    assert data['history']==data['sessions']==[]
    assert r.headers['cache-control']=='no-store'
    assert c.get('/api/v1/analytics?range=90d').status_code==422


def test_populated_weighted_metrics_alerts_risk_and_privacy(context):
    c,db,owner,other=context
    populate(db,owner,count=4,frames=2); populate(db,owner,count=10,frames=6)
    data=c.get('/api/v1/analytics').json()
    assert data['total_analyzed_videos']==data['total_live_sessions']==2
    assert data['video']['average_count']==data['live']['average_count']==8.5
    assert data['video']['peak_count']==11 and data['live']['peak_count']==12
    assert data['video']['average_image_occupancy']==.25
    assert data['video']['average_image_space_concentration']==.5
    assert data['live']['average_image_occupancy'] is None
    assert data['video']['crowd_levels']=={'LOW':8}
    assert data['alerts']=={'total':4,'by_severity':{'CRITICAL':2,'WARNING':2},'by_type':{'CROWD_COUNT_ABOVE':2,'ZONE_COUNT_ABOVE':2}}
    assert data['video']['risk_distribution']=={'CRITICAL':2}
    assert data['live']['risk_distribution']=={'HIGH':2}
    assert data['session_statuses']=={'STOPPED':2}
    assert data['peak_periods']['live']['live_peak']==12
    assert len(data['video_zones'])==2
    assert 'track_id' not in str(data) and 'storage_key' not in str(data)


def test_ownership(context):
    c,db,owner,other=context
    foreign=populate(db,other)
    assert c.get('/api/v1/analytics').json()['alerts']['total']==0
    assert c.get('/api/v1/analytics').json()['video_zones']==[]
    assert c.get('/api/v1/analytics/sessions/'+str(foreign.id)).status_code==404
    assert c.get('/api/v1/analytics/sessions/'+str(uuid.uuid4())).status_code==404


def test_time_ranges_use_source_cohorts(context):
    c,db,owner,other=context
    for days in (1,10,40):populate(db,owner,days=days)
    for period,total in [('7d',1),('30d',2),('all',3)]:
        data=c.get('/api/v1/analytics?range='+period).json()
        assert data['total_live_sessions']==data['total_analyzed_videos']==total
        assert data['alerts']['total']==2*total


def test_deterministic_summary_and_drilldown(context):
    c,db,owner,other=context
    session=populate(db,owner)
    url='/api/v1/analytics/sessions/'+str(session.id)
    first=c.get(url).json(); assert c.get(url).json()==first
    assert first['summary']=='Monitoring ran for 18.0 minutes. Peak observed crowd count was 6. Recorded alerts: 1 warning. Maximum rule-derived operational risk was HIGH.'
    assert first['duration_seconds']==1080
    assert first['zones']==[{'id':'entry','name':'Entrance Zone','peak_count':3}]
    assert first['final_operational_risk']=='NORMAL' and first['maximum_operational_risk']=='HIGH'
    assert first['peak_image_occupancy'] is None
    assert first['alert_history'][0]['zone_name']=='Entrance Zone'
    session.status='FAILED'; session.summary={}; db.commit()
    result=c.get(url).json()
    assert 'failure' in result['summary'] and result['peak_count'] is None
    session.status='RUNNING'; session.stopped_at=None; db.commit()
    assert c.get(url).json()['summary'] is None


def test_history_limits_do_not_truncate_totals(context):
    c,db,owner,other=context
    session=populate(db,owner)
    for _ in range(105):
        db.add(LiveAlertEvent(session_id=session.id,severity='INFO',rule_snapshot={'rule_type':'ZONE_PRESENCE'},evidence={}))
    db.commit()
    data=c.get('/api/v1/analytics/sessions/'+str(session.id)).json()
    assert len(data['alert_history'])==100 and data['alerts']['total']==106

