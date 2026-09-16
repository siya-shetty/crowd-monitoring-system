"""Strict public contracts for retrospective, user-configured operational alerts."""
from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

RuleType = Literal['CROWD_COUNT_ABOVE', 'CROWD_LEVEL_AT_LEAST', 'SUDDEN_CROWD_INCREASE', 'ZONE_COUNT_ABOVE', 'ZONE_PRESENCE']
Severity = Literal['INFO', 'WARNING', 'CRITICAL']
Scope = Literal['VIDEO', 'ZONE']
Risk = Literal['NORMAL', 'ELEVATED', 'HIGH', 'CRITICAL']
Level = Literal['LOW', 'MODERATE', 'HIGH', 'VERY_HIGH']


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False, from_attributes=True)


class DurationConfig(Contract):
    minimum_duration_seconds: float = Field(default=0, ge=0, strict=True)
    maximum_gap_seconds: float = Field(default=1, gt=0, strict=True)


class CountConfig(DurationConfig):
    threshold: int = Field(ge=1, strict=True)


class LevelConfig(DurationConfig):
    minimum_level: Level


class IncreaseConfig(DurationConfig):
    increase_count: int = Field(ge=1, strict=True)
    lookback_seconds: float = Field(gt=0, strict=True)


class PresenceConfig(DurationConfig):
    minimum_presence_count: int = Field(default=1, ge=1, strict=True)


CONFIGS = dict(CROWD_COUNT_ABOVE=CountConfig, CROWD_LEVEL_AT_LEAST=LevelConfig,
               SUDDEN_CROWD_INCREASE=IncreaseConfig, ZONE_COUNT_ABOVE=CountConfig, ZONE_PRESENCE=PresenceConfig)


class RuleCreate(Contract):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    rule_type: RuleType
    scope: Scope
    severity: Severity = 'WARNING'
    enabled: bool = Field(default=True, strict=True)
    zone_id: UUID | None = None
    configuration: dict

    @model_validator(mode='after')
    def validate_rule(self):
        if not self.name.strip():
            raise ValueError('Rule name must not be blank')
        zone = self.rule_type.startswith('ZONE_')
        if self.scope != ('ZONE' if zone else 'VIDEO') or zone != (self.zone_id is not None):
            raise ValueError('Zone rules require ZONE scope and zone_id; video rules require VIDEO scope without zone_id')
        self.configuration = CONFIGS[self.rule_type].model_validate(self.configuration).model_dump()
        return self


class RuleUpdate(Contract):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    rule_type: RuleType | None = None
    scope: Scope | None = None
    severity: Severity | None = None
    enabled: bool | None = Field(default=None, strict=True)
    zone_id: UUID | None = None
    configuration: dict | None = None


class RuleResponse(RuleCreate):
    id: UUID
    video_id: UUID
    created_at: datetime
    updated_at: datetime


class Evidence(Contract):
    metric: Literal['observed_crowd_count', 'crowd_level', 'crowd_count_increase', 'active_tracks_in_zone']
    operator: Literal['>='] = '>='
    threshold: int | Level
    trigger_value: int | Level
    peak_value: int | Level
    condition_start_seconds: float
    trigger_seconds: float
    last_observed_seconds: float
    minimum_duration_seconds: float
    maximum_gap_seconds: float
    observed_duration_seconds: float
    baseline_seconds: float | None = None
    baseline_count: int | None = None
    current_count: int | None = None
    zone_name: str | None = None
    closure: Literal['condition_false', 'observation_gap', 'end_of_analysis']


class EventResponse(Contract):
    id: UUID
    rule_id: UUID | None
    video_id: UUID
    zone_id: UUID | None
    rule_name: str
    rule_type: RuleType
    severity: Severity
    configuration: dict
    condition_start_seconds: float
    trigger_seconds: float
    end_seconds: float
    state: Literal['HISTORICAL']
    evidence: Evidence
    created_at: datetime


class AlertSummary(Contract):
    total_events: int
    events_by_severity: dict[Severity, int]
    events_by_rule_type: dict[RuleType, int]
    earliest_alert_seconds: float | None
    maximum_operational_risk: Risk
    configured_rules: int
    enabled_rules: int
