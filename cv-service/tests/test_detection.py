from types import SimpleNamespace

import pytest
import numpy as np

from app.detection.detector import PersonDetector
from app.video import processor


class Scalar:
    def __init__(self, value): self.value = value
    def item(self): return self.value

class Box:
    def __init__(self, cls, confidence, coords): self.cls = Scalar(cls); self.conf = Scalar(confidence); self.xyxy = [SimpleNamespace(tolist=lambda: coords)]

def test_detector_serializes_only_person_boxes() -> None:
    detector = PersonDetector.__new__(PersonDetector); detector.confidence = .35; detector.image_size = 640
    detector.model = lambda *args, **kwargs: [SimpleNamespace(names={0: 'person', 5: 'bus'}, boxes=[Box(0, .9, [1,2,3,4]), Box(5, .8, [5,6,7,8])])]
    assert detector.detect(object()) == [{'x1': 1.0, 'y1': 2.0, 'x2': 3.0, 'y2': 4.0, 'confidence': .9}]

def test_processor_preserves_stride_frame_indices_timestamps_and_summary(monkeypatch) -> None:
    class Capture:
        def __init__(self): self.index = 0
        def read(self):
            if self.index == 5: return False, None
            frame = np.zeros((10, 10, 3), dtype=np.uint8); self.index += 1; return True, frame
        def release(self): pass
    class Detector:
        def detect(self, frame): return [{'x1': 1., 'y1': 2., 'x2': 3., 'y2': 4., 'confidence': .8}]
    monkeypatch.setattr(processor, 'inspect', lambda path: {'width': 10, 'height': 10, 'fps': 2., 'frame_count': 5, 'duration_seconds': 2.5})
    monkeypatch.setattr(processor, 'get_detector', lambda *args: Detector())
    monkeypatch.setattr(processor.cv2, 'VideoCapture', lambda path: Capture())
    monkeypatch.setattr(processor.cv2, 'imencode', lambda *args: (False, None))
    result = processor.analyze_video('x', 'fake', .35, 640, 2)
    assert [f['frame_index'] for f in result['frames']] == [0, 2, 4]
    assert [f['timestamp_seconds'] for f in result['frames']] == [0., 1., 2.]
    assert result['sampled_frames_processed'] == 3 and result['frames_with_people'] == 3
    assert result['total_person_detections'] == 3 and result['maximum_persons_in_sampled_frame'] == 1
    assert result['average_persons_per_sampled_frame'] == 1.

def test_invalid_stride_is_rejected() -> None:
    with pytest.raises(ValueError): processor.analyze_video('x', 'fake', .35, 640, 0)
