from __future__ import annotations

import base64
import time
from pathlib import Path
from typing import Any

import cv2

from app.detection.detector import get_detector
from app.main import inspect


def analyze_video(path: Path, model_name: str, confidence: float, image_size: int, frame_stride: int) -> dict[str, Any]:
    if frame_stride < 1:
        raise ValueError("frame_stride must be at least 1")
    metadata = inspect(path)
    detector = get_detector(model_name, confidence, image_size)
    capture = cv2.VideoCapture(str(path))
    started = time.perf_counter()
    frames: list[dict[str, Any]] = []
    preview: str | None = None
    index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if index % frame_stride == 0:
            boxes = detector.detect(frame)
            item = {"frame_index": index, "timestamp_seconds": index / metadata["fps"], "person_count": len(boxes), "detections": boxes}
            frames.append(item)
            if preview is None and boxes:
                annotated = frame.copy()
                for box in boxes:
                    cv2.rectangle(annotated, (int(box["x1"]), int(box["y1"])), (int(box["x2"]), int(box["y2"])), (0, 255, 255), 2)
                success, encoded = cv2.imencode(".jpg", annotated)
                if success:
                    preview = base64.b64encode(encoded.tobytes()).decode("ascii")
        index += 1
    capture.release()
    total = sum(frame["person_count"] for frame in frames)
    return {**metadata, "model": model_name, "confidence_threshold": confidence, "frame_stride": frame_stride, "sampled_frames_processed": len(frames), "frames_with_people": sum(1 for frame in frames if frame["person_count"]), "total_person_detections": total, "maximum_persons_in_sampled_frame": max((frame["person_count"] for frame in frames), default=0), "average_persons_per_sampled_frame": total / len(frames) if frames else 0.0, "processing_duration_seconds": time.perf_counter() - started, "frames": frames, "annotated_preview_base64": preview}
