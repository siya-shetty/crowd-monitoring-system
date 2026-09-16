from datetime import datetime
from statistics import median
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, StringConstraints, model_validator
from app.schemas.tracking import Contract
from app.services.spatial_geometry import validate_polygon

Count = Annotated[int, Field(ge=0, strict=True)]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]


class Point(Contract):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class ZoneCreate(Contract):
    name: Name
    polygon: list[Point] = Field(min_length=3, max_length=50)
    description: Description | None = None
    active: bool = Field(default=True, strict=True)

    @model_validator(mode="after")
    def geometry(self):
        validate_polygon(self.polygon)
        return self


class ZoneUpdate(Contract):
    name: Name | None = None
    polygon: list[Point] | None = Field(default=None, min_length=3, max_length=50)
    description: Description | None = None
    active: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def valid_update(self):
        for key in ("name", "polygon", "active"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null")
        if self.polygon is not None:
            validate_polygon(self.polygon)
        return self


class Heatmap(Contract):
    schema_version: Literal[1] = 1
    grid_width: int = Field(ge=1, le=128, strict=True)
    grid_height: int = Field(ge=1, le=128, strict=True)
    raw_counts: list[list[Count]]
    total_valid_spatial_observations: Count
    maximum_cell_observation_count: Count
    hottest_cell: tuple[Count, Count] | None
    hottest_cell_center: Point | None

    @model_validator(mode="after")
    def consistent(self):
        if len(self.raw_counts) != self.grid_height or any(len(r) != self.grid_width for r in self.raw_counts):
            raise ValueError("Grid shape mismatch")
        flat = [c for row in self.raw_counts for c in row]
        maximum = max(flat)
        if sum(flat) != self.total_valid_spatial_observations or maximum != self.maximum_cell_observation_count:
            raise ValueError("Grid summary mismatch")
        index = flat.index(maximum)
        expected = (index % self.grid_width, index // self.grid_width) if maximum else None
        center = Point(x=(expected[0] + .5) / self.grid_width, y=(expected[1] + .5) / self.grid_height) if expected else None
        if self.hottest_cell != expected or self.hottest_cell_center != center:
            raise ValueError("Hottest cell mismatch")
        return self


class ZoneFrame(Contract):
    frame_index: Count
    timestamp_seconds: float = Field(ge=0)
    active_tracks_in_zone: Count
    track_ids_in_zone: list[Annotated[int, Field(gt=0, strict=True)]]

    @model_validator(mode="after")
    def counts(self):
        if self.active_tracks_in_zone != len(self.track_ids_in_zone) or self.track_ids_in_zone != sorted(set(self.track_ids_in_zone)):
            raise ValueError("Zone IDs/count mismatch")
        return self


class ZoneSummary(Contract):
    processed_frames: Count
    frames_with_people: Count
    maximum_simultaneous_tracks: Count
    average_simultaneous_tracks: float = Field(ge=0)
    median_simultaneous_tracks: float = Field(ge=0)
    earliest_peak_frame: Count | None
    earliest_peak_timestamp_seconds: float | None = Field(ge=0)
    distinct_anonymous_track_ids: Count
    total_track_observations: Count


def summarize(frames):
    counts = [f.active_tracks_in_zone for f in frames]
    maximum = max(counts, default=0)
    peak = frames[counts.index(maximum)] if frames else None
    return ZoneSummary(processed_frames=len(frames), frames_with_people=sum(c > 0 for c in counts),
        maximum_simultaneous_tracks=maximum, average_simultaneous_tracks=sum(counts) / len(counts) if counts else 0,
        median_simultaneous_tracks=median(counts) if counts else 0,
        earliest_peak_frame=peak.frame_index if peak else None,
        earliest_peak_timestamp_seconds=peak.timestamp_seconds if peak else None,
        distinct_anonymous_track_ids=len({i for f in frames for i in f.track_ids_in_zone}),
        total_track_observations=sum(counts))


class ZoneAnalysis(Contract):
    schema_version: Literal[1] = 1
    frames: list[ZoneFrame]
    summary: ZoneSummary

    @model_validator(mode="after")
    def consistent(self):
        if any(b.frame_index <= a.frame_index or b.timestamp_seconds <= a.timestamp_seconds for a, b in zip(self.frames, self.frames[1:])):
            raise ValueError("Zone frames must be chronological")
        if self.summary != summarize(self.frames):
            raise ValueError("Zone summary mismatch")
        return self


class ZoneResponse(ZoneCreate):
    model_config = ConfigDict(from_attributes=True, extra="forbid", allow_inf_nan=False)
    id: UUID
    video_id: UUID
    created_at: datetime
    updated_at: datetime
    analysis: ZoneAnalysis | None = None
