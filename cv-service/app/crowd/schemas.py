"""Versioned crowd wire contract; mirrored in backend/app/schemas/crowd.py.

Levels describe observed count, never safety. Summary statistics weight each
processed tracking frame equally. Peak ties select the earliest observation.
"""
import math
from statistics import mean, median
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Level = Literal["LOW", "MODERATE", "HIGH", "VERY_HIGH"]
Trend = Literal["increasing", "stable", "decreasing"]
LEVELS = ("LOW", "MODERATE", "HIGH", "VERY_HIGH")


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class CrowdConfig(Contract):
    moderate_count: int = Field(default=5, ge=1)
    high_count: int = Field(default=10, ge=1)
    very_high_count: int = Field(default=20, ge=1)
    trend_window_frames: Literal[10] = 10
    trend_min_change: Literal[1] = 1

    @model_validator(mode="after")
    def ordered(self):
        if not self.moderate_count < self.high_count < self.very_high_count:
            raise ValueError("Crowd count thresholds must be strictly increasing")
        return self

    def level(self, count: int) -> Level:
        if count >= self.very_high_count:
            return "VERY_HIGH"
        if count >= self.high_count:
            return "HIGH"
        if count >= self.moderate_count:
            return "MODERATE"
        return "LOW"


def count_trend(counts: list[int], config: CrowdConfig) -> Trend:
    """OLS fitted count change over the last 10 observations; no prediction."""
    if len(counts) < config.trend_window_frames:
        return "stable"
    values = counts[-config.trend_window_frames:]
    midpoint = (len(values) - 1) / 2
    slope = sum((i - midpoint) * value for i, value in enumerate(values)) / sum(
        (i - midpoint) ** 2 for i in range(len(values)))
    change = slope * (len(values) - 1)
    if change >= config.trend_min_change:
        return "increasing"
    if change <= -config.trend_min_change:
        return "decreasing"
    return "stable"


class CrowdFrame(Contract):
    frame_index: int = Field(ge=0, strict=True)
    timestamp_seconds: float = Field(ge=0)
    observed_crowd_count: int = Field(ge=0, strict=True)
    image_occupancy_ratio: float = Field(ge=0, le=1)
    crowd_concentration: float = Field(ge=0, le=1)
    crowd_level: Level
    crowd_count_delta: int = Field(strict=True)
    crowd_trend: Trend


class LevelDistribution(Contract):
    level: Level
    frames: int = Field(ge=0, strict=True)
    percentage: float = Field(ge=0, le=100)


class CrowdSummary(Contract):
    processed_crowd_frames: int = Field(ge=0, strict=True)
    frames_with_observed_people: int = Field(ge=0, strict=True)
    minimum_observed_crowd_count: int = Field(ge=0, strict=True)
    maximum_observed_crowd_count: int = Field(ge=0, strict=True)
    average_observed_crowd_count: float = Field(ge=0)
    median_observed_crowd_count: float = Field(ge=0)
    peak_crowd_frame: int | None = Field(ge=0, strict=True)
    peak_crowd_timestamp_seconds: float | None = Field(ge=0)
    average_image_occupancy: float = Field(ge=0, le=1)
    maximum_image_occupancy: float = Field(ge=0, le=1)
    peak_occupancy_frame: int | None = Field(ge=0, strict=True)
    peak_occupancy_timestamp_seconds: float | None = Field(ge=0)
    average_crowd_concentration: float = Field(ge=0, le=1)
    maximum_crowd_concentration: float = Field(ge=0, le=1)
    level_distribution: list[LevelDistribution]
    final_crowd_trend: Trend


def summarize(frames: list[CrowdFrame]) -> CrowdSummary:
    counts = [f.observed_crowd_count for f in frames]
    occupancy = [f.image_occupancy_ratio for f in frames]
    concentration = [f.crowd_concentration for f in frames]
    peak = max(frames, key=lambda f: f.observed_crowd_count, default=None)
    occupied = max(frames, key=lambda f: f.image_occupancy_ratio, default=None)
    return CrowdSummary(
        processed_crowd_frames=len(frames), frames_with_observed_people=sum(c > 0 for c in counts),
        minimum_observed_crowd_count=min(counts, default=0), maximum_observed_crowd_count=max(counts, default=0),
        average_observed_crowd_count=mean(counts) if counts else 0,
        median_observed_crowd_count=median(counts) if counts else 0,
        peak_crowd_frame=peak.frame_index if peak else None,
        peak_crowd_timestamp_seconds=peak.timestamp_seconds if peak else None,
        average_image_occupancy=mean(occupancy) if occupancy else 0,
        maximum_image_occupancy=max(occupancy, default=0),
        peak_occupancy_frame=occupied.frame_index if occupied else None,
        peak_occupancy_timestamp_seconds=occupied.timestamp_seconds if occupied else None,
        average_crowd_concentration=mean(concentration) if concentration else 0,
        maximum_crowd_concentration=max(concentration, default=0),
        level_distribution=[LevelDistribution(level=level,
            frames=sum(f.crowd_level == level for f in frames),
            percentage=100 * sum(f.crowd_level == level for f in frames) / len(frames) if frames else 0)
            for level in LEVELS],
        final_crowd_trend=frames[-1].crowd_trend if frames else "stable")


def check_summary(actual, expected):
    if isinstance(expected, dict):
        if actual.keys() != expected.keys():
            raise ValueError("Inconsistent crowd summary fields")
        for key in expected:
            check_summary(actual[key], expected[key])
    elif isinstance(expected, list):
        if len(actual) != len(expected):
            raise ValueError("Inconsistent crowd distribution")
        for a, e in zip(actual, expected):
            check_summary(a, e)
    elif isinstance(expected, float):
        if not math.isclose(actual, expected, rel_tol=1e-9, abs_tol=1e-9):
            raise ValueError("Inconsistent crowd statistic")
    elif actual != expected:
        raise ValueError("Inconsistent crowd summary")


class CrowdAnalysis(Contract):
    schema_version: Literal[1] = 1
    config: CrowdConfig
    frames: list[CrowdFrame]
    summary: CrowdSummary

    @model_validator(mode="after")
    def consistent(self):
        counts = []
        previous = None
        for frame in self.frames:
            if previous and (frame.frame_index <= previous.frame_index or
                             frame.timestamp_seconds <= previous.timestamp_seconds):
                raise ValueError("Crowd frames must be chronological")
            count = frame.observed_crowd_count
            delta = count - counts[-1] if counts else 0
            counts.append(count)
            if frame.crowd_count_delta != delta or frame.crowd_level != self.config.level(count):
                raise ValueError("Inconsistent crowd delta or level")
            if frame.crowd_trend != count_trend(counts, self.config):
                raise ValueError("Inconsistent crowd trend")
            if count == 0 and frame.image_occupancy_ratio != 0:
                raise ValueError("Empty crowd must have zero occupancy")
            if count < 2 and frame.crowd_concentration != 0:
                raise ValueError("Concentration requires at least two tracks")
            previous = frame
        check_summary(self.summary.model_dump(), summarize(self.frames).model_dump())
        return self
