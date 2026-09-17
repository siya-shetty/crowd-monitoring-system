from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import Field, model_validator
from app.schemas.alerts import Contract, RuleCreate
from app.schemas.spatial import Name, Description, ZoneCreate
from app.schemas.tracking import TrackedPerson


class CameraCreate(Contract):
    name: Name
    description: Description | None = None
    source_type: Literal['BROWSER'] = 'BROWSER'
    source_configuration: dict = Field(default_factory=dict, max_length=0)
    enabled: bool = Field(default=True, strict=True)


class CameraUpdate(Contract):
    name: Name | None = None
    description: Description | None = None
    enabled: bool | None = Field(default=None, strict=True)

    @model_validator(mode='after')
    def nonnull(self):
        if any(k in self.model_fields_set and getattr(self, k) is None for k in ('name', 'enabled')):
            raise ValueError('Name and enabled cannot be null')
        return self


class CameraResponse(CameraCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime


class CameraZoneResponse(ZoneCreate):
    model_config = {'from_attributes': True, 'extra': 'forbid', 'allow_inf_nan': False}
    id: UUID
    camera_id: UUID


class CameraRuleCreate(RuleCreate):
    scope: Literal['CAMERA', 'ZONE']

    @model_validator(mode='after')
    def validate_rule(self):
        # Keep the Phase 8 validation authoritative; CAMERA maps to whole-source VIDEO.
        data = self.model_dump(include=set(RuleCreate.model_fields))
        data['scope'] = 'VIDEO' if self.scope == 'CAMERA' else self.scope
        self.configuration = RuleCreate.model_validate(data).configuration
        if self.configuration.get('lookback_seconds', 0) > 60:
            raise ValueError('Live lookback is limited to 60 seconds')
        return self


class CameraRuleResponse(CameraRuleCreate):
    id: UUID
    camera_id: UUID


class FrameObservation(Contract):
    sequence: int = Field(ge=1)
    capture_timestamp: float = Field(ge=0)
    width: int = Field(ge=16, le=1920)
    height: int = Field(ge=16, le=1920)
    tracks: list[TrackedPerson] = Field(max_length=1000)
    observed_crowd_count: int = Field(ge=0)
    image_occupancy_ratio: float = Field(ge=0, le=1)
    crowd_concentration: float = Field(ge=0, le=1)
    crowd_level: Literal['LOW', 'MODERATE', 'HIGH', 'VERY_HIGH']
    crowd_count_delta: int
    crowd_trend: Literal['increasing', 'stable', 'decreasing']
    processing_duration_seconds: float = Field(ge=0)

    @model_validator(mode='after')
    def consistent(self):
        if len(self.tracks) != self.observed_crowd_count or len({t.track_id for t in self.tracks}) != len(self.tracks):
            raise ValueError('Invalid track count')
        return self


class SessionResponse(Contract):
    id: UUID
    camera_id: UUID
    status: Literal['STARTING','RUNNING','STOPPING','STOPPED','FAILED']
    started_at: datetime
    stopped_at: datetime | None
    last_frame_at: datetime | None
    processed_frame_count: int
    dropped_frame_count: int
    error_summary: str | None
    latest_snapshot: dict | None
    summary: dict
    created_at: datetime
    updated_at: datetime
