from __future__ import annotations

from functools import lru_cache
from typing import Any


PERSON_CLASS_NAME = "person"


class PersonDetector:
    """Process-wide lazy Ultralytics loader; no identity or tracking state."""

    def __init__(self, model_name: str, confidence: float, image_size: int) -> None:
        self.model_name = model_name
        self.confidence = confidence
        self.image_size = image_size
        from ultralytics import YOLO
        self.model: Any = YOLO(model_name)

    def detect(self, frame: Any) -> list[dict[str, float]]:
        result = self.model(frame, conf=self.confidence, imgsz=self.image_size, verbose=False)[0]
        names = result.names
        detections: list[dict[str, float]] = []
        for box in result.boxes:
            class_id = int(box.cls.item())
            if names[class_id] != PERSON_CLASS_NAME:
                continue
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
            detections.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": float(box.conf.item())})
        return detections


@lru_cache
def get_detector(model_name: str, confidence: float, image_size: int) -> PersonDetector:
    return PersonDetector(model_name, confidence, image_size)
