import uuid
import importlib.util
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy import text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.session import engine
from app.main import app
from app.db.session import SessionLocal
from app.models.video import Video
from app.models.zone import MonitoringZone
from test_videos import register_and_login
from test_tracking import payload, mock_cv
from test_spatial_math import SQUARE


def test_zone_crud_security_persistence_no_inference_and_cascade(monkeypatch):
    data=payload();mock_cv(monkeypatch,data)
    client=TestClient(app);owner=register_and_login();other=register_and_login()
    item=client.post('/api/v1/videos',headers=owner,files={'file':('zones.mp4',b'test','video/mp4')}).json()
    assert item['status']=='completed'
    assert item['heatmap_analysis']['total_valid_spatial_observations']==sum(f['active_track_count'] for f in data['tracking']['frames'])
    assert item['detection_frames']==data['frames'] and item['tracking_analysis']==data['tracking'] and item['crowd_analysis']==data['crowd']
    base=f"/api/v1/videos/{item['id']}";url=base+'/zones'
    def forbidden(*args,**kwargs): raise AssertionError('Spatial changes must never call inference')
    monkeypatch.setattr('app.services.video_processing.httpx.post',forbidden)
    monkeypatch.setattr('app.api.v1.videos.analyze_video',forbidden)
    for headers,code in [({},401),(other,404)]:
        assert client.get(url,headers=headers).status_code==code
        assert client.post(url,headers=headers,json={'name':'A','polygon':SQUARE}).status_code==code
        assert client.post(base+'/heatmap',headers=headers).status_code==code
    result=client.post(url,headers=owner,json={'name':'Path','polygon':SQUARE,'description':'Test'})
    assert result.status_code==201,result.text
    zone=result.json();detail=url+'/'+zone['id']
    assert zone['analysis'] is not None
    with SessionLocal() as db:
        stored=db.get(MonitoringZone,uuid.UUID(zone['id']))
        assert stored.analysis==zone['analysis']
        assert db.get(Video,uuid.UUID(item['id'])).heatmap_analysis==item['heatmap_analysis']
    for headers,code in [({},401),(other,404)]:
        assert client.get(detail,headers=headers).status_code==code
        assert client.patch(detail,headers=headers,json={'name':'stolen'}).status_code==code
        assert client.delete(detail,headers=headers).status_code==code
    assert client.get(detail,headers=owner).json()==zone
    assert client.get(url,headers=owner).json()==[zone]
    full=[dict(x=x,y=y) for x,y in [(0,0),(1,0),(1,1),(0,1)]]
    edited=client.patch(detail,headers=owner,json={'polygon':full}).json()
    assert edited['analysis']['summary']['total_track_observations']==item['heatmap_analysis']['total_valid_spatial_observations']
    renamed=client.patch(detail,headers=owner,json={'name':'<script>plain text</script>','description':None}).json()
    assert renamed['analysis']==edited['analysis'] and renamed['description'] is None
    assert client.patch(detail,headers=owner,json={'active':False}).json()['analysis'] is None
    assert client.patch(detail,headers=owner,json={'active':True}).json()['analysis']==edited['analysis']
    with SessionLocal() as db:
        video=db.get(Video,uuid.UUID(item['id']));video.heatmap_analysis=None;db.commit()
    assert client.post(base+'/heatmap',headers=owner).json()==item['heatmap_analysis']
    for invalid in [[],SQUARE[:2],SQUARE+[SQUARE[0]],[{'x':2,'y':0}]+SQUARE[1:]]:
        assert client.post(url,headers=owner,json={'name':'bad','polygon':invalid}).status_code==422
        assert client.patch(detail,headers=owner,json={'polygon':invalid}).status_code==422
    assert client.get(url+'/invalid',headers=owner).status_code==422
    assert client.get(url+'/'+str(uuid.uuid4()),headers=owner).status_code==404
    assert client.get('/api/v1/videos/'+str(uuid.uuid4())+'/zones',headers=owner).status_code==404
    second=client.post(url,headers=owner,json={'name':'Second','polygon':full}).json()
    assert client.delete(detail,headers=owner).status_code==204
    assert client.get(detail,headers=owner).status_code==404
    assert client.delete(base,headers=owner).status_code==204
    with SessionLocal() as db:
        assert db.get(Video,uuid.UUID(item['id'])) is None
        assert db.get(MonitoringZone,uuid.UUID(second['id'])) is None
        assert list(db.scalars(select(MonitoringZone).where(MonitoringZone.video_id==uuid.UUID(item['id']))))==[]


def test_spatial_migration_upgrade_downgrade_preserves_phase6():
    path=Path(__file__).resolve().parents[1]/'alembic/versions/20260916_06_add_spatial_analysis.py'
    spec=importlib.util.spec_from_file_location('spatial_migration',path)
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    assert migration.down_revision=='20260915_05'
    # Isolate all DDL in a disposable transactional schema, never downgrade live tables.
    schema='migration_test_'+uuid.uuid4().hex
    with engine.connect() as connection:
        transaction=connection.begin()
        try:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
            connection.execute(text(f'SET LOCAL search_path TO {schema}'))
            connection.execute(text('CREATE TABLE videos (id UUID PRIMARY KEY, crowd_analysis JSON, tracking_analysis JSON)'))
            video_id=uuid.uuid4()
            connection.execute(text("INSERT INTO videos VALUES (:id, CAST(:c AS JSON), CAST(:t AS JSON))"),{'id':video_id,'c':'{"count":2}','t':'{"tracks":2}'})
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert connection.execute(text('SELECT heatmap_analysis FROM videos')).scalar_one() is None
                connection.execute(text("INSERT INTO monitoring_zones (id,video_id,name,polygon,active) VALUES (:id,:v,'Test','[]',true)"),{'id':uuid.uuid4(),'v':video_id})
                connection.execute(text('DELETE FROM videos'))
                assert connection.execute(text('SELECT count(*) FROM monitoring_zones')).scalar_one()==0
                migration.downgrade()
                connection.execute(text("INSERT INTO videos VALUES (:id, CAST(:c AS JSON), CAST(:t AS JSON))"),{'id':video_id,'c':'{"count":2}','t':'{"tracks":2}'})
                migration.upgrade()
                assert connection.execute(text('SELECT crowd_analysis FROM videos')).scalar_one()=={'count':2}
                assert connection.execute(text('SELECT tracking_analysis FROM videos')).scalar_one()=={'tracks':2}
        finally:
            transaction.rollback()
