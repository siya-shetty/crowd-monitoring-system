import uuid
from datetime import datetime
from enum import StrEnum
from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
class VideoStatus(StrEnum): UPLOADED="uploaded"; PROCESSING="processing"; COMPLETED="completed"; FAILED="failed"
class Video(Base):
    __tablename__="videos"
    id: Mapped[uuid.UUID]=mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID]=mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    owner: Mapped["User"] = relationship(back_populates="videos")
    original_filename: Mapped[str]=mapped_column(String(255), nullable=False); storage_key: Mapped[str]=mapped_column(String(255), unique=True, nullable=False); content_type: Mapped[str]=mapped_column(String(100), nullable=False); file_size: Mapped[int]=mapped_column(Integer, nullable=False)
    status: Mapped[VideoStatus]=mapped_column(Enum(VideoStatus, name="video_status", values_callable=lambda values:[value.value for value in values]), nullable=False, default=VideoStatus.UPLOADED)
    duration_seconds: Mapped[float|None]=mapped_column(Float); width: Mapped[int|None]=mapped_column(Integer); height: Mapped[int|None]=mapped_column(Integer); fps: Mapped[float|None]=mapped_column(Float); frame_count: Mapped[int|None]=mapped_column(Integer); error_message: Mapped[str|None]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now()); updated_at: Mapped[datetime]=mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()); processing_started_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True)); processing_completed_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True))
