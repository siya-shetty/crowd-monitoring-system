"""Caller holds the video row lock; rebuilds occur inside its transaction."""
from sqlalchemy import delete, select
from app.models.alert import AlertRule, AlertEvent
from app.models.zone import MonitoringZone
from app.schemas.alerts import RuleCreate
from app.services.alert_engine import evaluate


def rebuild(database, video, rule, zone=None):
    if not rule.enabled:
        return  # Disabled rules retain historical evidence, including risk contribution.
    if rule.zone_id and zone is None:
        zone = database.get(MonitoringZone, rule.zone_id)
    source = zone.analysis if zone else video.crowd_analysis
    evidence = evaluate(RuleCreate.model_validate(rule), source['frames'] if source else [], zone.name if zone else None)
    database.execute(delete(AlertEvent).where(AlertEvent.rule_id == rule.id))
    for item in evidence:
        database.add(AlertEvent(rule_id=rule.id, video_id=video.id, zone_id=rule.zone_id,
            rule_name=rule.name, rule_type=rule.rule_type, severity=rule.severity,
            configuration=dict(rule.configuration), condition_start_seconds=item['condition_start_seconds'],
            trigger_seconds=item['trigger_seconds'], end_seconds=item['last_observed_seconds'], evidence=item))


def rebuild_zone_rules(database, video, zone):
    for rule in database.scalars(select(AlertRule).where(AlertRule.zone_id == zone.id, AlertRule.enabled.is_(True))):
        rebuild(database, video, rule, zone)
