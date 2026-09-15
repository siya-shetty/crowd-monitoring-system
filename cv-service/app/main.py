import os
import tempfile
from pathlib import Path
from typing import Any

import cv2
from fastapi import FastAPI, File, HTTPException, UploadFile

app = FastAPI(title="Crowd Monitoring CV Service", version="0.3.0")


def inspect(path: Path) -> dict[str, float | int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise ValueError("Unreadable video")
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)); height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(capture.get(cv2.CAP_PROP_FPS)); frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT)); capture.release()
    if width <= 0 or height <= 0 or fps <= 0 or frames <= 0:
        raise ValueError("Invalid video metadata")
    return {"width": width, "height": height, "fps": fps, "frame_count": frames, "duration_seconds": frames / fps}


def with_upload(file: UploadFile, operation: Any) -> dict[str, Any]:
    suffix = Path(file.filename or "video.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as temporary:
        temporary.write(file.file.read()); path = Path(temporary.name)
    try: return operation(path)
    except ValueError as error: raise HTTPException(status_code=422, detail="Video could not be analyzed") from error
    except Exception: raise HTTPException(status_code=503, detail="Detection service unavailable") from None
    finally: path.unlink(missing_ok=True)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]: return {"status": "ok", "service": "crowd-monitoring-cv-service", "mode": "person-detection"}


@app.post("/inspect")
def inspect_upload(file: UploadFile = File(...)) -> dict[str, float | int]: return with_upload(file, inspect)


@app.post("/analyze")
def analyze_upload(file: UploadFile = File(...)) -> dict[str, Any]:
    from app.video.processor import analyze_video
    model = os.getenv("YOLO_MODEL", "yolo11n.pt")
    confidence = float(os.getenv("YOLO_CONFIDENCE_THRESHOLD", "0.35"))
    image_size = int(os.getenv("YOLO_IMAGE_SIZE", "640")); stride = int(os.getenv("YOLO_FRAME_STRIDE", "5"))
    if not 0 < confidence <= 1 or image_size < 32 or stride < 1:
        raise HTTPException(status_code=422, detail="Invalid inference configuration")
    return with_upload(file, lambda path: analyze_video(path, model, confidence, image_size, stride))
