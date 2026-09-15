"""Person-only ByteTrack adapter with an instance-local ID allocator."""
from types import SimpleNamespace
import numpy as np
from app.tracking.config import TrackingConfig
from app.tracking.schemas import PersonBox, TrackedPerson


class PersonTracker:
    def __init__(self, config: TrackingConfig, width: int, height: int):
        from ultralytics.engine.results import Boxes
        from ultralytics.trackers.byte_tracker import BYTETracker, STrack

        # Upstream BaseTrack uses a process-global counter. Override its allocator
        # through track_class so even interleaved analyses own independent IDs.
        class LocalTrack(STrack):
            counter = 0

            @staticmethod
            def next_id():
                LocalTrack.counter += 1
                return LocalTrack.counter

        class LocalByteTracker(BYTETracker):
            track_class = LocalTrack

            @staticmethod
            def reset_id():
                LocalTrack.counter = 0

        self._tracker = LocalByteTracker(SimpleNamespace(
            **config.model_dump(exclude={"frame_stride"}),
            new_track_thresh=config.track_high_thresh, fuse_score=True))
        self._boxes = Boxes
        self.width, self.height = width, height

    def update(self, detections: list[dict[str, float]]) -> list[TrackedPerson]:
        persons = [PersonBox.model_validate(box) for box in detections]
        data = np.asarray([[p.x1, p.y1, p.x2, p.y2, p.confidence, 0]
                           for p in persons], dtype=np.float32).reshape(-1, 6)
        rows = self._tracker.update(self._boxes(data, (self.height, self.width)))
        output = []
        for row in rows:
            if len(row) != 8 or not np.isfinite(row).all():
                raise ValueError("Invalid tracker output")
            x1, y1, x2, y2, track_id, confidence, cls, detection_index = row
            if cls != 0 or track_id < 1 or track_id != int(track_id):
                raise ValueError("Invalid person track")
            if detection_index != int(detection_index) or not 0 <= detection_index < len(persons):
                raise ValueError("Track is not associated with a retained detection")
            output.append(TrackedPerson(track_id=int(track_id),
                x1=max(0., float(x1)), y1=max(0., float(y1)),
                x2=min(float(self.width), float(x2)), y2=min(float(self.height), float(y2)),
                confidence=float(confidence)))
        if len({p.track_id for p in output}) != len(output):
            raise ValueError("Duplicate track IDs")
        return output
