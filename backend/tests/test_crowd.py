import importlib.util
from pathlib import Path
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from alembic.migration import MigrationContext
from alembic.operations import Operations
from app.db.session import SessionLocal, engine
from app.main import app
from app.models.video import Video
from app.schemas.analysis import AnalysisResponse
from app.services.video_storage import VideoStorage
from test_tracking import payload, mock_cv
from test_videos import register_and_login


@pytest.mark.parametrize('mutation', [
    lambda p: p.pop('crowd'),
    lambda p: p['crowd']['frames'][0].update(frame_index=-1),
    lambda p: p['crowd']['frames'][0].update(timestamp_seconds=float('inf')),
    lambda p: p['crowd']['frames'][0].update(observed_crowd_count=-1),
    lambda p: p['crowd']['frames'][0].update(image_occupancy_ratio=1.01),
    lambda p: p['crowd']['frames'][0].update(image_occupancy_ratio=-.1),
    lambda p: p['crowd']['frames'][0].update(crowd_concentration=1.01),
    lambda p: p['crowd']['frames'][0].update(crowd_concentration=float('nan')),
    lambda p: p['crowd']['frames'][0].update(crowd_level='DANGER'),
    lambda p: p['crowd']['frames'][0].update(crowd_level='HIGH'),
    lambda p: p['crowd']['frames'][1].update(crowd_count_delta=1),
    lambda p: p['crowd']['frames'][1].update(crowd_trend='increasing'),
    lambda p: p['crowd']['summary'].update(average_observed_crowd_count=4),
    lambda p: p['crowd']['summary'].update(median_observed_crowd_count=4),
    lambda p: p['crowd']['summary'].update(minimum_observed_crowd_count=0),
    lambda p: p['crowd']['summary'].update(peak_crowd_frame=1),
    lambda p: p['crowd']['summary'].update(peak_crowd_timestamp_seconds=.1),
    lambda p: p['crowd']['summary'].update(peak_occupancy_frame=1),
    lambda p: p['crowd']['summary'].update(maximum_image_occupancy=.5),
    lambda p: p['crowd']['summary']['level_distribution'][0].update(frames=99),
    lambda p: p['crowd']['summary']['level_distribution'][0].update(percentage=90),
    lambda p: p['crowd']['frames'].pop(),
    lambda p: p['crowd']['config'].update(high_count=4),
])
def test_malformed_crowd_rejected(mutation):
    data = payload()
    mutation(data)
    with pytest.raises(ValueError): AnalysisResponse.model_validate(data)


def test_crowd_persistence_owner_regression_and_cleanup(monkeypatch):
    data = payload()
    mock_cv(monkeypatch, data)
    client = TestClient(app)
    owner, other = register_and_login(), register_and_login()
    item = client.post('/api/v1/videos', headers=owner, files={'file':('crowd.mp4',b'test','video/mp4')}).json()
    assert item['status'] == 'completed'
    assert item['crowd_analysis'] == data['crowd']
    assert item['tracking_analysis'] == data['tracking']
    assert item['detection_frames'] == data['frames']
    url = f"/api/v1/videos/{item['id']}"
    with SessionLocal() as db:
        stored = db.get(Video, uuid.UUID(item['id']))
        assert stored.crowd_analysis == data['crowd']
        paths = [VideoStorage().path_for(stored.storage_key), VideoStorage().path_for(stored.preview_storage_key)]
    assert client.get(url,headers=owner).json()['crowd_analysis'] == data['crowd']
    assert client.get('/api/v1/videos',headers=owner).json()[0]['crowd_analysis'] == data['crowd']
    assert client.get(url,headers=other).status_code == 404
    assert client.get(url).status_code == 401
    assert client.delete(url,headers=owner).status_code == 204
    assert not any(p.exists() for p in paths)
    with SessionLocal() as db:
        assert db.get(Video, uuid.UUID(item['id'])) is None


def test_malformed_crowd_fails_atomically(monkeypatch):
    data = payload()
    data['crowd']['summary']['peak_crowd_frame'] = 999
    mock_cv(monkeypatch,data)
    owner = register_and_login()
    client = TestClient(app)
    item = client.post('/api/v1/videos',headers=owner,files={'file':('bad.mp4',b'test','video/mp4')}).json()
    assert item['status'] == 'failed'
    assert item['crowd_analysis'] is item['tracking_analysis'] is item['detection_summary'] is None
    assert not item['has_annotated_preview']
    assert client.delete(f"/api/v1/videos/{item['id']}",headers=owner).status_code == 204


def test_crowd_contract_mirror_and_migration_compatibility():
    root = Path(__file__).resolve().parents[2]
    assert (root/'cv-service/app/crowd/schemas.py').read_bytes() == (root/'backend/app/schemas/crowd.py').read_bytes()
    spec = importlib.util.spec_from_file_location('crowd_migration',root/'backend/alembic/versions/20260915_05_add_video_crowd.py')
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == '20260915_04'
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text('CREATE TEMP TABLE videos (detection_summary JSON, tracking_analysis JSON) ON COMMIT DROP'))
            connection.execute(text("INSERT INTO videos VALUES (CAST(:d AS JSON), CAST(:t AS JSON))"),
                               {"d": '{"detections":3}', "t": '{"tracks":2}'})
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert connection.execute(text('SELECT crowd_analysis FROM videos')).scalar_one() is None
                migration.downgrade()
                assert connection.execute(text('SELECT tracking_analysis FROM videos')).scalar_one() == {'tracks':2}
                assert connection.execute(text('SELECT detection_summary FROM videos')).scalar_one() == {'detections':3}
                migration.upgrade()
        finally:
            transaction.rollback()
