from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any
import cv2

from app.detection.detector import get_detector
from app.main import inspect
from app.tracking.config import TrackingConfig
from app.tracking.tracker import PersonTracker
from app.tracking.schemas import TrackingFrame
from app.tracking.aggregation import aggregate
from app.crowd.aggregation import aggregate as aggregate_crowd
from app.crowd.schemas import CrowdConfig


def analyze_video(path: Path, model_name: str, confidence: float, image_size: int,
                  frame_stride: int, tracking_config: TrackingConfig | None = None,
                  crowd_config: CrowdConfig | None = None) -> dict[str, Any]:
    if frame_stride < 1:
        raise ValueError("frame_stride must be at least 1")
    config = tracking_config or TrackingConfig()
    metadata = inspect(path)
    detector = get_detector(model_name, min(confidence, config.track_low_thresh), image_size)
    tracker = PersonTracker(config, metadata["width"], metadata["height"])
    capture = cv2.VideoCapture(str(path))
    started = time.perf_counter()
    frames: list[dict[str, Any]] = []
    tracking_frames: list[TrackingFrame] = []
    preview: str | None = None
    preview_has_tracks = False
    index = 0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            detection_sample = index % frame_stride == 0
            tracking_sample = index % config.frame_stride == 0
            if detection_sample or tracking_sample:
                boxes = detector.detect(frame)
                retained = [box for box in boxes if box["confidence"] >= confidence]
                if detection_sample:
                    frames.append({"frame_index": index, "timestamp_seconds": index / metadata["fps"],
                                   "person_count": len(retained), "detections": retained})
                if tracking_sample:
                    tracked = tracker.update([box for box in boxes if box["confidence"] >= config.track_low_thresh])
                    tracking_frames.append(TrackingFrame(frame_index=index, timestamp_seconds=index / metadata["fps"],
                        active_track_count=len(tracked), tracked_persons=tracked))
                else:
                    tracked = []
                if (tracked and not preview_has_tracks) or (preview is None and retained):
                    annotated = frame.copy()
                    for box in (tracked or retained):
                        values = box.model_dump() if hasattr(box, "model_dump") else box
                        cv2.rectangle(annotated, (int(values["x1"]), int(values["y1"])),
                                      (int(values["x2"]), int(values["y2"])), (0, 255, 255), 2)
                        label = f"Track {values['track_id']}" if "track_id" in values else "Person"
                        cv2.putText(annotated, label, (int(values["x1"]), max(18, int(values["y1"]) - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 255, 255), 2)
                    success, encoded = cv2.imencode(".jpg", annotated)
                    if success:
                        preview = base64.b64encode(encoded.tobytes()).decode("ascii")
                        preview_has_tracks = bool(tracked)
            index += 1
    finally:
        capture.release()
    if index != metadata["frame_count"]:
        raise ValueError("Video decoding ended before all frames were processed")
    total = sum(frame["person_count"] for frame in frames)
    tracking = aggregate(tracking_frames, metadata["width"], metadata["height"], config)
    crowd = aggregate_crowd(tracking_frames, metadata["width"], metadata["height"], crowd_config or CrowdConfig())
    return {**metadata, "model": Path(model_name).name, "confidence_threshold": confidence,
        "frame_stride": frame_stride, "sampled_frames_processed": len(frames),
        "frames_with_people": sum(1 for frame in frames if frame["person_count"]),
        "total_person_detections": total,
        "maximum_persons_in_sampled_frame": max((frame["person_count"] for frame in frames), default=0),
        "average_persons_per_sampled_frame": total / len(frames) if frames else 0.0,
        "processing_duration_seconds": time.perf_counter() - started, "frames": frames,
        "tracking": tracking.model_dump(mode="json"), "crowd": crowd.model_dump(mode="json"),
        "annotated_preview_base64": preview}
