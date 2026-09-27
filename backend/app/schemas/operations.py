from datetime import datetime
from typing import Literal
from uuid import UUID
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_serializer, model_validator
from app.schemas.alerts import Severity

IncidentStatus = Literal['OPEN', 'INVESTIGATING', 'RESOLVED', 'CLOSED']


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True, str_strip_whitespace=True)


class IncidentInput(Contract):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default='', max_length=4000)
    severity: Severity = 'WARNING'
    status: IncidentStatus = 'OPEN'
    occurred_at: AwareDatetime
    resolved_at: AwareDatetime | None = None
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

    @field_serializer('context')
    def monitoring_context(self, context):
        # Retain legacy event snapshots in storage, without exposing a retired feature.
        return {key: value for key, value in context.items() if key != 'event'}
