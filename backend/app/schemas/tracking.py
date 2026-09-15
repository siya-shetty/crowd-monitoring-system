"""Versioned wire contract; mirrored in backend/app/schemas/tracking.py.

Coordinates are image pixels for boxes and normalized [0, 1] for trajectories.
Only observed, confirmed tracks are active; lost predictions are not observations.
"""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class PersonBox(Contract):
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(gt=0)
    y2: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def ordered_box(self):
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("Degenerate bounding box")
        return self


class TrackedPerson(PersonBox):
    track_id: int = Field(gt=0, strict=True)


class TrackingFrame(Contract):
    frame_index: int = Field(ge=0, strict=True)
    timestamp_seconds: float = Field(ge=0)
    active_track_count: int = Field(ge=0, strict=True)
    tracked_persons: list[TrackedPerson]

    @model_validator(mode="after")
    def counts(self):
        ids = [person.track_id for person in self.tracked_persons]
        if self.active_track_count != len(ids) or len(set(ids)) != len(ids):
            raise ValueError("Invalid active track count or duplicate IDs")
        return self


class TrajectoryPoint(Contract):
    frame_index: int = Field(ge=0, strict=True)
    timestamp_seconds: float = Field(ge=0)
    center_x: float = Field(ge=0, le=1)
    center_y: float = Field(ge=0, le=1)


class TrackHistory(Contract):
    track_id: int = Field(gt=0, strict=True)
    first_observed_frame: int = Field(ge=0, strict=True)
    last_observed_frame: int = Field(ge=0, strict=True)
    first_observed_timestamp: float = Field(ge=0)
    last_observed_timestamp: float = Field(ge=0)
    observation_count: int = Field(gt=0, strict=True)
    average_confidence: float = Field(ge=0, le=1)
    trajectory: list[TrajectoryPoint]


class TrackingSummary(Contract):
    tracker: Literal["ByteTrack"] = "ByteTrack"
    frame_stride: int = Field(ge=1, strict=True)
    track_high_threshold: float = Field(gt=0, le=1)
    track_low_threshold: float = Field(ge=0, lt=1)
    track_match_threshold: float = Field(gt=0, le=1)
    track_buffer: int = Field(ge=1, strict=True)
    processed_frames: int = Field(ge=0, strict=True)
    frames_with_active_tracks: int = Field(ge=0, strict=True)
    maximum_simultaneous_active_tracks: int = Field(ge=0, strict=True)
    average_active_tracks_per_processed_frame: float = Field(ge=0)
    distinct_track_ids: int = Field(ge=0, strict=True)
    average_track_observation_length: float = Field(ge=0)
    longest_track_observation_length: int = Field(ge=0, strict=True)


class TrackingAnalysis(Contract):
    schema_version: Literal[1] = 1
    summary: TrackingSummary
    frames: list[TrackingFrame]
    tracks: list[TrackHistory]
