import base64
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.video import Video, VideoStatus
from app.services.video_storage import VideoStorage

SUMMARY_KEYS = {"model", "confidence_threshold", "frame_stride", "sampled_frames_processed", "frames_with_people", "total_person_detections", "maximum_persons_in_sampled_frame", "average_persons_per_sampled_frame", "processing_duration_seconds"}


def analyze_video(database: Session, video: Video) -> Video:
    video.status = VideoStatus.PROCESSING; video.processing_started_at = datetime.now(UTC); database.commit()
    try:
        with VideoStorage().path_for(video.storage_key).open("rb") as content:
            response = httpx.post(f"{get_settings().cv_service_url}/analyze", files={"file": (video.original_filename, content, video.content_type)}, timeout=180)
        response.raise_for_status(); payload: dict[str, Any] = response.json()
        if not SUMMARY_KEYS <= payload.keys() or not isinstance(payload.get("frames"), list):
            raise ValueError("Malformed CV response")
        for field in ("width", "height", "fps", "frame_count", "duration_seconds"):
            if field not in payload: raise ValueError("Malformed CV response")
        video.width = int(payload["width"]); video.height = int(payload["height"]); video.fps = float(payload["fps"]); video.frame_count = int(payload["frame_count"]); video.duration_seconds = float(payload["duration_seconds"])
        video.detection_summary = {key: payload[key] for key in SUMMARY_KEYS}
        video.detection_frames = payload["frames"]
        preview = payload.get("annotated_preview_base64")
        if preview:
            key = f"{video.id}-preview.jpg"; path = VideoStorage().path_for(key); path.write_bytes(base64.b64decode(preview, validate=True)); video.preview_storage_key = key
        video.status = VideoStatus.COMPLETED; video.error_message = None
    except Exception:
        video.status = VideoStatus.FAILED; video.error_message = "Video detection analysis could not be completed"
    video.processing_completed_at = datetime.now(UTC); database.commit(); database.refresh(video); return video
