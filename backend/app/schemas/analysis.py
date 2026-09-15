"""Validate the entire CV response before writing any analysis or preview."""
import math
from collections import defaultdict
from typing import Self
from pydantic import Field, model_validator
from app.schemas.tracking import Contract, PersonBox, TrackingAnalysis


class DetectionFrame(Contract):
    frame_index: int = Field(ge=0, strict=True)
    timestamp_seconds: float = Field(ge=0)
    person_count: int = Field(ge=0, strict=True)
    detections: list[PersonBox]


class AnalysisResponse(Contract):
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    fps: float = Field(gt=0)
    frame_count: int = Field(gt=0, strict=True)
    duration_seconds: float = Field(gt=0)
    model: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$", max_length=100)
    confidence_threshold: float = Field(gt=0, le=1)
    frame_stride: int = Field(ge=1, strict=True)
    sampled_frames_processed: int = Field(ge=0, strict=True)
    frames_with_people: int = Field(ge=0, strict=True)
    total_person_detections: int = Field(ge=0, strict=True)
    maximum_persons_in_sampled_frame: int = Field(ge=0, strict=True)
    average_persons_per_sampled_frame: float = Field(ge=0)
    processing_duration_seconds: float = Field(ge=0)
    frames: list[DetectionFrame]
    tracking: TrackingAnalysis
    annotated_preview_base64: str | None = None

    @model_validator(mode="after")
    def consistent_analysis(self) -> Self:
        def same(actual, expected):
            if not math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-6):
                raise ValueError("Inconsistent analysis")

        same(self.duration_seconds, self.frame_count / self.fps)
        summary = self.tracking.summary
        if summary.track_low_threshold >= summary.track_high_threshold:
            raise ValueError("Invalid tracker thresholds")
        for frames, stride in ((self.frames, self.frame_stride), (self.tracking.frames, summary.frame_stride)):
            if len(frames) != (self.frame_count - 1) // stride + 1:
                raise ValueError("Incomplete sampled frames")
            for index, frame in enumerate(frames):
                same(frame.frame_index, index * stride)
                same(frame.timestamp_seconds, frame.frame_index / self.fps)
                boxes = frame.detections if isinstance(frame, DetectionFrame) else frame.tracked_persons
                for box in boxes:
                    if box.x2 > self.width or box.y2 > self.height:
                        raise ValueError("Out-of-image box")
        counts = [len(f.detections) for f in self.frames]
        for f in self.frames:
            same(f.person_count, len(f.detections))
            if any(p.confidence < self.confidence_threshold for p in f.detections):
                raise ValueError("Detection below threshold")
        same(self.sampled_frames_processed, len(counts))
        same(self.frames_with_people, sum(c > 0 for c in counts))
        same(self.total_person_detections, sum(counts))
        same(self.maximum_persons_in_sampled_frame, max(counts, default=0))
        same(self.average_persons_per_sampled_frame, sum(counts) / len(counts) if counts else 0)
        observations = defaultdict(list)
        for f in self.tracking.frames:
            for p in f.tracked_persons:
                if p.confidence < summary.track_low_threshold:
                    raise ValueError("Track below threshold")
                observations[p.track_id].append((f, p))
        ids = [t.track_id for t in self.tracking.tracks]
        if len(set(ids)) != len(ids) or set(ids) != set(observations):
            raise ValueError("Inconsistent track histories")
        for t in self.tracking.tracks:
            items = observations[t.track_id]
            same(t.observation_count, len(items))
            same(t.first_observed_frame, items[0][0].frame_index)
            same(t.last_observed_frame, items[-1][0].frame_index)
            same(t.first_observed_timestamp, items[0][0].timestamp_seconds)
            same(t.last_observed_timestamp, items[-1][0].timestamp_seconds)
            same(t.average_confidence, sum(p.confidence for _, p in items) / len(items))
            if len(t.trajectory) != len(items):
                raise ValueError("Incomplete trajectory")
            for point, (f, p) in zip(t.trajectory, items):
                same(point.frame_index, f.frame_index)
                same(point.timestamp_seconds, f.timestamp_seconds)
                same(point.center_x, (p.x1 + p.x2) / (2 * self.width))
                same(point.center_y, (p.y1 + p.y2) / (2 * self.height))
        counts = [f.active_track_count for f in self.tracking.frames]
        lengths = [len(items) for items in observations.values()]
        same(summary.processed_frames, len(counts))
        same(summary.frames_with_active_tracks, sum(c > 0 for c in counts))
        same(summary.maximum_simultaneous_active_tracks, max(counts, default=0))
        same(summary.average_active_tracks_per_processed_frame, sum(counts) / len(counts) if counts else 0)
        same(summary.distinct_track_ids, len(ids))
        same(summary.longest_track_observation_length, max(lengths, default=0))
        same(summary.average_track_observation_length, sum(lengths) / len(lengths) if lengths else 0)
        return self
