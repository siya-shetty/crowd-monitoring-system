import base64
import copy
from pathlib import Path
from types import SimpleNamespace
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from app.main import app
from app.db.session import SessionLocal
from app.models.video import Video
from app.services import video_processing
from app.services.video_storage import VideoStorage
from app.schemas.analysis import AnalysisResponse
from test_videos import register_and_login


def payload():
    box = dict(x1=1., y1=2., x2=3., y2=4., confidence=.8)
    frames = [dict(frame_index=i, timestamp_seconds=i / 10, active_track_count=1,
                   tracked_persons=[dict(track_id=1, **box)]) for i in range(2)]
    return dict(width=10, height=10, fps=10., frame_count=2, duration_seconds=.2,
        model='yolo11n.pt', confidence_threshold=.35, frame_stride=1, sampled_frames_processed=2,
        frames_with_people=2, total_person_detections=2, maximum_persons_in_sampled_frame=1,
        average_persons_per_sampled_frame=1., processing_duration_seconds=.1,
        frames=[dict(frame_index=i, timestamp_seconds=i / 10, person_count=1, detections=[box]) for i in range(2)],
        annotated_preview_base64=base64.b64encode(b'\xff\xd8test\xff\xd9').decode(),
        tracking=dict(schema_version=1, summary=dict(tracker='ByteTrack', frame_stride=1, track_high_threshold=.25,
            track_low_threshold=.1, track_match_threshold=.8, track_buffer=30, processed_frames=2,
            frames_with_active_tracks=2, maximum_simultaneous_active_tracks=1,
            average_active_tracks_per_processed_frame=1., distinct_track_ids=1,
            average_track_observation_length=2., longest_track_observation_length=2), frames=frames,
            tracks=[dict(track_id=1, first_observed_frame=0, last_observed_frame=1,
                first_observed_timestamp=0., last_observed_timestamp=.1, observation_count=2,
                average_confidence=.8, trajectory=[dict(frame_index=i, timestamp_seconds=i / 10,
                    center_x=.2, center_y=.3) for i in range(2)])]))


def mock_cv(monkeypatch, data):
    monkeypatch.setattr(video_processing.httpx, 'post', lambda *a, **kw:
        SimpleNamespace(raise_for_status=lambda: None, json=lambda: copy.deepcopy(data)))


def test_tracking_persistence_ownership_preview_and_delete(monkeypatch):
    client = TestClient(app)
    data = payload()
    mock_cv(monkeypatch, data)
    owner, other = register_and_login(), register_and_login()
    response = client.post('/api/v1/videos', headers=owner, files={'file': ('tracking.mp4', b'test', 'video/mp4')})
    assert response.status_code == 201
    item = response.json()
    assert item['status'] == 'completed'
    assert item['tracking_analysis'] == data['tracking']
    assert item['detection_frames'] == data['frames']
    assert item['detection_summary']['total_person_detections'] == 2
    assert all(key not in response.text for key in ['storage_key', 'base64', 'private-path', 'track_class'])
    url = f"/api/v1/videos/{item['id']}"
    with SessionLocal() as db:
        stored = db.get(Video, uuid.UUID(item['id']))
        paths = [VideoStorage().path_for(stored.storage_key), VideoStorage().path_for(stored.preview_storage_key)]
        assert all(path.exists() for path in paths)
        assert stored.tracking_analysis == data['tracking']
    assert client.get(url, headers=owner).json()['tracking_analysis'] == data['tracking']
    assert client.get('/api/v1/videos', headers=owner).json()[0]['tracking_analysis'] == data['tracking']
    assert client.get(url + '/preview', headers=owner).status_code == 200
    assert client.get(url + '/preview').status_code == 401
    for suffix in ['', '/preview']:
        assert client.get(url + suffix, headers=other).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    assert client.delete(url, headers=owner).status_code == 204
    assert not any(path.exists() for path in paths)


@pytest.mark.parametrize('mutation', [
    lambda p: p.pop('tracking'),
    lambda p: p['tracking']['summary'].update(distinct_track_ids=99),
    lambda p: p['tracking']['frames'][0].update(active_track_count=4),
    lambda p: p['tracking']['frames'][0]['tracked_persons'][0].update(track_id=-1),
    lambda p: p['tracking']['frames'][0]['tracked_persons'][0].update(confidence=float('nan')),
    lambda p: p['tracking']['frames'][0]['tracked_persons'][0].update(x2=999),
    lambda p: p['tracking']['tracks'][0]['trajectory'][0].update(center_x=.9),
    lambda p: p['tracking']['tracks'][0].update(observation_count=5),
    lambda p: p['tracking']['frames'][1].update(timestamp_seconds=7),
    lambda p: p['tracking']['summary'].update(private_path='/private-path'),
    lambda p: p.update(model='/private-path/model.pt'),
    lambda p: p['frames'][0].update(person_count=9),
    lambda p: p['tracking']['summary'].update(average_active_tracks_per_processed_frame=9),
    lambda p: p['tracking']['frames'].reverse(),
])
def test_malformed_contract_rejected(mutation):
    data = payload()
    mutation(data)
    with pytest.raises(ValueError): AnalysisResponse.model_validate(data)


@pytest.mark.parametrize('failure', ['malformed', 'preview', 'service'])
def test_failed_analysis_is_safe_and_atomic(monkeypatch, failure):
    data = payload()
    if failure == 'malformed': data['tracking']['summary']['distinct_track_ids'] = -1
    if failure == 'preview': data['annotated_preview_base64'] = 'bad-base64/private-path'
    mock_cv(monkeypatch, data)
    if failure == 'service':
        def fail(*a, **kw): raise RuntimeError('/private-path traceback')
        monkeypatch.setattr(video_processing.httpx, 'post', fail)
    client = TestClient(app)
    owner = register_and_login()
    response = client.post('/api/v1/videos', headers=owner, files={'file': ('bad.mp4', b'test', 'video/mp4')})
    item = response.json()
    assert item['status'] == 'failed'
    assert item['processing_completed_at']
    assert item['tracking_analysis'] is None and item['detection_summary'] is None
    assert not item['has_annotated_preview']
    assert 'private-path' not in response.text and 'traceback' not in response.text
    assert client.delete(f"/api/v1/videos/{item['id']}", headers=owner).status_code == 204


def test_migration_head_and_contract_mirror():
    root = Path(__file__).resolve().parents[2]
    assert (root / 'cv-service/app/tracking/schemas.py').read_bytes() == (root / 'backend/app/schemas/tracking.py').read_bytes()
    with SessionLocal() as db:
        assert db.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '20260915_04'
        assert db.execute(text("SELECT is_nullable FROM information_schema.columns WHERE table_name='videos' AND column_name='tracking_analysis'")).scalar_one() == 'YES'


def test_phase5_migration_upgrade_downgrade_preserves_detection_data():
    import importlib.util
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from app.db.session import engine
    path = Path(__file__).resolve().parents[1] / 'alembic/versions/20260915_04_add_video_tracking.py'
    spec = importlib.util.spec_from_file_location('phase5_migration', path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            # A connection-local temp table shadows the real table. No production
            # schema or user data is downgraded during this regression check.
            connection.execute(text('CREATE TEMP TABLE videos (detection_summary JSON) ON COMMIT DROP'))
            connection.execute(text("INSERT INTO videos VALUES ('{\"total_person_detections\": 3}')"))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                assert connection.execute(text('SELECT tracking_analysis FROM videos')).scalar_one() is None
                migration.downgrade()
                assert connection.execute(text('SELECT detection_summary FROM videos')).scalar_one() == {'total_person_detections': 3}
                migration.upgrade()
        finally:
            transaction.rollback()
