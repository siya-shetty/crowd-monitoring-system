from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict
from app.models.video import VideoStatus
from app.schemas.tracking import TrackingAnalysis
class VideoResponse(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id: UUID; original_filename: str; content_type: str; file_size: int; status: VideoStatus; duration_seconds: float|None; width: int|None; height: int|None; fps: float|None; frame_count: int|None; error_message: str|None; created_at: datetime; processing_started_at: datetime|None; processing_completed_at: datetime|None
    detection_summary: dict | None = None
    detection_frames: list | None = None
    has_annotated_preview: bool = False
    tracking_analysis: TrackingAnalysis | None = None
