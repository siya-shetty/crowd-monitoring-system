import os
from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal


class TrackingConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    tracker_type: Literal["bytetrack"] = "bytetrack"
    frame_stride: int = Field(default=1, ge=1)
    track_high_thresh: float = Field(default=0.25, gt=0, le=1)
    track_low_thresh: float = Field(default=0.1, ge=0, lt=1)
    match_thresh: float = Field(default=0.8, gt=0, le=1)
    track_buffer: int = Field(default=30, ge=1, le=1000)

    @model_validator(mode="after")
    def ordered_thresholds(self):
        if self.track_low_thresh >= self.track_high_thresh:
            raise ValueError("Low threshold must be below high threshold")
        return self

    @classmethod
    def from_environment(cls):
        names = {"tracker_type": "TRACKER_TYPE", "frame_stride": "TRACK_FRAME_STRIDE",
                 "track_high_thresh": "TRACK_HIGH_THRESHOLD", "track_low_thresh": "TRACK_LOW_THRESHOLD",
                 "match_thresh": "TRACK_MATCH_THRESHOLD", "track_buffer": "TRACK_BUFFER"}
        return cls(**{key: os.environ[name] for key, name in names.items() if name in os.environ})
