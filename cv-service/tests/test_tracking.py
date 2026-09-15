from types import SimpleNamespace
import numpy as np
import pytest
from app.tracking.config import TrackingConfig
from app.tracking.schemas import TrackedPerson, TrackingFrame
from app.tracking.aggregation import aggregate
from app.tracking.tracker import PersonTracker
from app.video import processor


def person(track_id=1, x1=10.):
    return TrackedPerson(track_id=track_id, x1=x1, y1=10, x2=x1 + 10, y2=30, confidence=.8)


def test_history_metrics_centers_and_empty_frames():
    frames = [TrackingFrame(frame_index=0, timestamp_seconds=0, active_track_count=1, tracked_persons=[person()]),
              TrackingFrame(frame_index=2, timestamp_seconds=.2, active_track_count=2, tracked_persons=[person(x1=20), person(2)]),
              TrackingFrame(frame_index=4, timestamp_seconds=.4, active_track_count=0, tracked_persons=[])]
    result = aggregate(frames, 100, 100, TrackingConfig(frame_stride=2))
    s = result.summary
    assert (s.processed_frames, s.frames_with_active_tracks, s.distinct_track_ids) == (3, 2, 2)
    assert s.maximum_simultaneous_active_tracks == 2
    assert s.average_active_tracks_per_processed_frame == 1
    assert s.average_track_observation_length == 1.5
    assert s.longest_track_observation_length == 2
    t = result.tracks[0]
    assert (t.first_observed_frame, t.last_observed_frame, t.observation_count) == (0, 2, 2)
    assert (t.first_observed_timestamp, t.last_observed_timestamp) == (0, .2)
    assert [(p.center_x, p.center_y) for p in t.trajectory] == [(.15, .2), (.25, .2)]
    assert t.average_confidence == .8
    assert aggregate([], 100, 100, TrackingConfig()).summary.distinct_track_ids == 0
    assert aggregate([frames[-1]], 100, 100, TrackingConfig()).tracks == []


@pytest.mark.parametrize('config', [dict(frame_stride=0), dict(track_buffer=0), dict(track_high_thresh=.1),
    dict(track_low_thresh=float('nan')), dict(match_thresh=1.1), dict(tracker_type='botsort')])
def test_invalid_config(config):
    with pytest.raises(ValueError): TrackingConfig(**config)


@pytest.mark.parametrize('row', [[0, 0, 10, 20, -1, .8, 0, 0], [0, 0, 10, 20, 1, .8, 2, 0],
    [0, 0, 10, 20, 1, float('nan'), 0, 0], [0, 0, 10, 20, 1, .8, 0, 8],
    [0, 0, 10, 20, 1.5, .8, 0, 0], [0, 0, 0, 20, 1, .8, 0, 0], [1, 2]])
def test_invalid_tracker_output(row):
    tracker = PersonTracker.__new__(PersonTracker)
    tracker.width = tracker.height = 100
    tracker._boxes = lambda data, shape: data
    tracker._tracker = SimpleNamespace(update=lambda boxes: np.array([row]))
    with pytest.raises(ValueError): tracker.update([person().model_dump(exclude={'track_id'})])


def test_tracker_receives_person_class_only_and_empty_input():
    tracker = PersonTracker.__new__(PersonTracker)
    tracker.width = tracker.height = 100
    tracker._boxes = lambda data, shape: data
    seen = []
    tracker._tracker = SimpleNamespace(update=lambda boxes: seen.append(boxes) or [])
    tracker.update([person().model_dump(exclude={'track_id'})])
    tracker.update([])
    assert seen[0][0, 5] == 0
    assert seen[1].shape == (0, 6)
    with pytest.raises(ValueError): tracker.update([{'class_id': 2, **person().model_dump(exclude={'track_id'})}])


@pytest.mark.parametrize('tracking_stride', [1, 2])
def test_processor_fake_continuity_sampling_and_isolation(monkeypatch, tracking_stride):
    captures, trackers, inference = [], [], []
    class Capture:
        def __init__(self): self.index = 0; self.released = False; captures.append(self)
        def read(self):
            self.index += 1
            return (True, np.zeros((100,100,3), dtype=np.uint8)) if self.index <= 5 else (False, None)
        def release(self): self.released = True
    class Tracker:
        def __init__(self, *args): self.calls = 0; trackers.append(self)
        def update(self, boxes):
            self.calls += 1
            return [person(x1=10 + self.calls)]
    def detect(frame):
        inference.append(1)
        return [person().model_dump(exclude={'track_id'})]
    monkeypatch.setattr(processor, 'inspect', lambda path: dict(width=100, height=100, fps=10., frame_count=5, duration_seconds=.5))
    monkeypatch.setattr(processor, 'get_detector', lambda *a: SimpleNamespace(detect=detect))
    monkeypatch.setattr(processor, 'PersonTracker', Tracker)
    monkeypatch.setattr(processor.cv2, 'VideoCapture', lambda path: Capture())
    monkeypatch.setattr(processor.cv2, 'imencode', lambda *args: (False, None))
    for _ in range(2):
        result = processor.analyze_video('x', 'fake', .35, 640, 2, TrackingConfig(frame_stride=tracking_stride))
        assert [f['frame_index'] for f in result['frames']] == [0, 2, 4]
        assert [f['timestamp_seconds'] for f in result['tracking']['frames']] == [i / 10 for i in range(0, 5, tracking_stride)]
        assert result['tracking']['tracks'][0]['observation_count'] == len(range(0, 5, tracking_stride))
        assert result['tracking']['tracks'][0]['track_id'] == 1
    assert len(trackers) == 2 and trackers[0] is not trackers[1]
    assert len(inference) == 2 * len(range(0, 5, tracking_stride))  # no duplicate inference
    assert all(c.released for c in captures)
    monkeypatch.setattr(Tracker, 'update', lambda self, boxes: [])
    monkeypatch.setattr(processor, 'get_detector', lambda *a: SimpleNamespace(detect=lambda frame: []))
    empty = processor.analyze_video('x', 'fake', .35, 640, 2)
    assert empty['tracking']['summary']['processed_frames'] == 5
    assert empty['tracking']['summary']['average_active_tracks_per_processed_frame'] == 0
    assert empty['tracking']['tracks'] == [] and empty['annotated_preview_base64'] is None
    def fail(self, boxes): raise ValueError('private tracker detail')
    monkeypatch.setattr(Tracker, 'update', fail)
    with pytest.raises(ValueError): processor.analyze_video('x', 'fake', .35, 640, 2)
    assert captures[-1].released


def test_invalid_environment_is_safe(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setenv('TRACK_HIGH_THRESHOLD', 'private-invalid')
    response = TestClient(app).post('/analyze', files={'file': ('x.mp4', b'x', 'video/mp4')})
    assert response.status_code == 422
    assert 'private-invalid' not in response.text
