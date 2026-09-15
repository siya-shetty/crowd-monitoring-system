import base64
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.video import Video, VideoStatus
from app.services.video_storage import VideoStorage
from app.schemas.analysis import AnalysisResponse

SUMMARY_KEYS = {"model", "confidence_threshold", "frame_stride", "sampled_frames_processed", "frames_with_people", "total_person_detections", "maximum_persons_in_sampled_frame", "average_persons_per_sampled_frame", "processing_duration_seconds"}


def analyze_video(database: Session, video: Video) -> Video:
    video.status = VideoStatus.PROCESSING; video.processing_started_at = datetime.now(UTC); database.commit()
    preview_key = None
    try:
        with VideoStorage().path_for(video.storage_key).open("rb") as content:
            response = httpx.post(f"{get_settings().cv_service_url}/analyze", files={"file": (video.original_filename, content, video.content_type)}, timeout=get_settings().cv_analysis_timeout_seconds)
        response.raise_for_status()
        payload: dict[str, Any] = AnalysisResponse.model_validate(response.json()).model_dump(mode="json")
        video.width = int(payload["width"]); video.height = int(payload["height"]); video.fps = float(payload["fps"]); video.frame_count = int(payload["frame_count"]); video.duration_seconds = float(payload["duration_seconds"])
        video.detection_summary = {key: payload[key] for key in SUMMARY_KEYS}
        video.detection_frames = payload["frames"]
        video.tracking_analysis = payload["tracking"]
        preview = payload.get("annotated_preview_base64")
        if preview:
            data = base64.b64decode(preview, validate=True)
            if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                raise ValueError("Invalid preview")
            preview_key = f"{video.id}-preview.jpg"
            VideoStorage().path_for(preview_key).write_bytes(data)
            video.preview_storage_key = preview_key
        video.status = VideoStatus.COMPLETED; video.error_message = None
        video.processing_completed_at = datetime.now(UTC)
        database.commit()
    except Exception:
        database.rollback()
        if preview_key:
            VideoStorage().delete(preview_key)
        video.status = VideoStatus.FAILED; video.error_message = "Video detection and tracking analysis could not be completed"
        video.processing_completed_at = datetime.now(UTC)
        database.commit()
    database.refresh(video)
    return video
