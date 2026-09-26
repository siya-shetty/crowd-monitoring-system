from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from app.schemas.alerts import Severity

EventStatus = Literal['PLANNED', 'ACTIVE', 'COMPLETED', 'CANCELLED']
IncidentStatus = Literal['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True, str_strip_whitespace=True)


class EventInput(Contract):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    location: str | None = Field(default=None, max_length=200)
    start_time: AwareDatetime
    end_time: AwareDatetime | None = None
    status: EventStatus = 'PLANNED'

    @model_validator(mode='after')
    def times(self):
        if self.end_time and self.end_time < self.start_time:
            raise ValueError('End time must be on or after start time')
        return self


class EventResponse(EventInput):
    id: UUID
    created_at: datetime
    updated_at: datetime


class IncidentInput(Contract):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=4000)
    severity: Severity = 'WARNING'
    status: IncidentStatus = 'OPEN'
    occurred_at: AwareDatetime
    resolved_at: AwareDatetime | None = None
    event_id: UUID | None = None
    camera_id: UUID | None = None
    video_id: UUID | None = None
    live_session_id: UUID | None = None
    alert_event_id: UUID | None = None
    live_alert_event_id: UUID | None = None

    @model_validator(mode='after')
    def valid(self):
        if self.alert_event_id and self.live_alert_event_id:
            raise ValueError('Choose one source alert')
        if self.resolved_at and self.resolved_at < self.occurred_at:
            raise ValueError('Resolution cannot precede occurrence')
        return self


class IncidentResponse(IncidentInput):
    id: UUID
    context: dict
    created_at: datetime
    updated_at: datetime
