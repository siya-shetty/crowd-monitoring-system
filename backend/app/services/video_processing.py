from datetime import UTC, datetime
import httpx
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.video import Video, VideoStatus
from app.services.video_storage import VideoStorage
def inspect_video(database: Session, video: Video) -> Video:
    video.status=VideoStatus.PROCESSING; video.processing_started_at=datetime.now(UTC); database.commit()
    try:
        path=VideoStorage().path_for(video.storage_key)
        with path.open("rb") as content: response=httpx.post(f"{get_settings().cv_service_url}/inspect", files={"file":(video.original_filename,content,video.content_type)}, timeout=30)
        response.raise_for_status(); metadata=response.json()
        video.width=metadata["width"]; video.height=metadata["height"]; video.fps=metadata["fps"]; video.frame_count=metadata["frame_count"]; video.duration_seconds=metadata["duration_seconds"]; video.status=VideoStatus.COMPLETED; video.processing_completed_at=datetime.now(UTC); video.error_message=None
    except Exception:
        video.status=VideoStatus.FAILED; video.error_message="Video inspection could not be completed"; video.processing_completed_at=datetime.now(UTC)
    database.commit(); database.refresh(video); return video
