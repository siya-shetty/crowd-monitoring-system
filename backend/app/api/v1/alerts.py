from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from sqlalchemy import select, func
from app.api.v1.dependencies import DatabaseSession
from app.api.v1.videos import CurrentUser, owned
from app.api.v1.zones import locked_video, zone_for
from app.models.alert import AlertRule, AlertEvent
from app.models.video import Video
from app.schemas.alerts import RuleCreate, RuleUpdate, RuleResponse, EventResponse, AlertSummary, Severity, RuleType
from app.services.alerts import rebuild
from app.services.alert_engine import operational_risk

router = APIRouter(tags=['alerts'])
base = '/videos/{video_id}'


def find_rule(database, video_id, rule_id):
    rule = database.scalar(select(AlertRule).where(AlertRule.video_id == video_id, AlertRule.id == rule_id))
    if rule is None:
        raise HTTPException(404, 'Alert rule not found')
    return rule


def validate_zone(database, video_id, payload):
    if payload.zone_id:
        zone_for(database, video_id, payload.zone_id)


@router.post(base+'/alert-rules', response_model=RuleResponse, status_code=201)
def create_rule(video_id: UUID, payload: RuleCreate, database: DatabaseSession, user: CurrentUser):
    video = locked_video(database, user, video_id)
    validate_zone(database, video_id, payload)
    if database.scalar(select(func.count()).select_from(AlertRule).where(AlertRule.video_id == video_id)) >= 100:
        raise HTTPException(409, 'At most 100 rules per video')
    rule = AlertRule(video_id=video_id, **payload.model_dump())
    database.add(rule)
    database.flush()
    rebuild(database, video, rule)
    database.commit()
    return rule


@router.get(base+'/alert-rules', response_model=list[RuleResponse])
def list_rules(video_id: UUID, database: DatabaseSession, user: CurrentUser):
    owned(database, user, video_id)
    return list(database.scalars(select(AlertRule).where(AlertRule.video_id == video_id).order_by(AlertRule.created_at, AlertRule.id)))


@router.get(base+'/alert-rules/{rule_id}', response_model=RuleResponse)
def get_rule(video_id: UUID, rule_id: UUID, database: DatabaseSession, user: CurrentUser):
    owned(database, user, video_id)
    return find_rule(database, video_id, rule_id)


@router.patch(base+'/alert-rules/{rule_id}', response_model=RuleResponse)
def update_rule(video_id: UUID, rule_id: UUID, payload: RuleUpdate, database: DatabaseSession, user: CurrentUser):
    video = locked_video(database, user, video_id)
    rule = find_rule(database, video_id, rule_id)
    try:
        validated = RuleCreate.model_validate(RuleCreate.model_validate(rule).model_dump() | payload.model_dump(exclude_unset=True))
    except ValidationError:
        raise HTTPException(422, 'Invalid rule fields, configuration, or scope') from None
    validate_zone(database, video_id, validated)
    for key, value in validated.model_dump().items():
        setattr(rule, key, value)
    rebuild(database, video, rule)
    database.commit()
    return rule


@router.post(base+'/alert-rules/{rule_id}/evaluate', response_model=RuleResponse)
def evaluate_rule(video_id: UUID, rule_id: UUID, database: DatabaseSession, user: CurrentUser):
    video = locked_video(database, user, video_id)
    rule = find_rule(database, video_id, rule_id)
    rebuild(database, video, rule)
    database.commit()
    return rule


@router.delete(base+'/alert-rules/{rule_id}', status_code=204)
def delete_rule(video_id: UUID, rule_id: UUID, database: DatabaseSession, user: CurrentUser):
    locked_video(database, user, video_id)
    database.delete(find_rule(database, video_id, rule_id))
    database.commit()


def events_query(user, video_id=None, severity=None, rule_type=None, zone_id=None, rule_id=None):
    query = select(AlertEvent).join(Video).where(Video.owner_id == user.id)
    for column, value in ((AlertEvent.video_id, video_id), (AlertEvent.severity, severity),
                          (AlertEvent.rule_type, rule_type), (AlertEvent.zone_id, zone_id), (AlertEvent.rule_id, rule_id)):
        if value is not None:
            query = query.where(column == value)
    return query.order_by(AlertEvent.created_at.desc(), AlertEvent.trigger_seconds, AlertEvent.id)


@router.get('/alerts', response_model=list[EventResponse])
def global_events(database: DatabaseSession, user: CurrentUser, severity: Severity | None = None, rule_type: RuleType | None = None):
    return list(database.scalars(events_query(user, severity=severity, rule_type=rule_type)))


@router.get(base+'/alerts', response_model=list[EventResponse])
def video_events(video_id: UUID, database: DatabaseSession, user: CurrentUser, severity: Severity | None = None,
                 rule_type: RuleType | None = None, zone_id: UUID | None = None, rule_id: UUID | None = None):
    owned(database, user, video_id)
    return list(database.scalars(events_query(user, video_id, severity, rule_type, zone_id, rule_id)))


@router.get(base+'/alerts/{alert_id}', response_model=EventResponse)
def get_event(video_id: UUID, alert_id: UUID, database: DatabaseSession, user: CurrentUser):
    owned(database, user, video_id)
    item = database.scalar(events_query(user, video_id).where(AlertEvent.id == alert_id))
    if item is None:
        raise HTTPException(404, 'Alert event not found')
    return item


@router.get(base+'/alert-summary', response_model=AlertSummary)
def summary(video_id: UUID, database: DatabaseSession, user: CurrentUser):
    rules = list_rules(video_id, database, user)
    events = list(database.scalars(events_query(user, video_id)))
    return dict(total_events=len(events), events_by_severity={s: sum(e.severity == s for e in events) for s in ('INFO', 'WARNING', 'CRITICAL')},
        events_by_rule_type={t: sum(e.rule_type == t for e in events) for t in ('CROWD_COUNT_ABOVE', 'CROWD_LEVEL_AT_LEAST', 'SUDDEN_CROWD_INCREASE', 'ZONE_COUNT_ABOVE', 'ZONE_PRESENCE')},
        earliest_alert_seconds=min((e.trigger_seconds for e in events), default=None),
        maximum_operational_risk=operational_risk(e.severity for e in events), configured_rules=len(rules), enabled_rules=sum(r.enabled for r in rules))
