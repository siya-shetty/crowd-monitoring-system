import uuid
import pytest
from pydantic import ValidationError
from app.schemas.alerts import RuleCreate
from app.services.alert_engine import evaluate, operational_risk


def rule(kind='CROWD_COUNT_ABOVE', **config):
    return RuleCreate(name='Test', rule_type=kind, scope='ZONE' if kind.startswith('ZONE') else 'VIDEO',
        zone_id=uuid.uuid4() if kind.startswith('ZONE') else None, configuration=config)


def frames(counts, times=None):
    return [dict(frame_index=i, timestamp_seconds=t, observed_crowd_count=c, image_occupancy_ratio=0,
        crowd_concentration=0, crowd_level='VERY_HIGH' if c>=20 else 'HIGH' if c>=10 else 'MODERATE' if c>=5 else 'LOW',
        crowd_count_delta=0, crowd_trend='stable') for i,(c,t) in enumerate(zip(counts,times or range(len(counts))))]


@pytest.mark.parametrize('count,expected', [(0,0),(1,0),(2,1),(3,1)])
def test_count_boundary(count,expected):
    assert len(evaluate(rule(threshold=2),frames([count])))==expected


@pytest.mark.parametrize('count,expected',[(5,0),(10,1),(20,1)])
def test_level(count,expected):
    assert len(evaluate(rule('CROWD_LEVEL_AT_LEAST',minimum_level='HIGH'),frames([count])))==expected


@pytest.mark.parametrize('kind,config', [('ZONE_COUNT_ABOVE',{'threshold':1}),('ZONE_PRESENCE',{})])
@pytest.mark.parametrize('count',[0,1,3])
def test_zone(kind,config,count):
    data=[dict(frame_index=0,timestamp_seconds=0,active_tracks_in_zone=count,track_ids_in_zone=list(range(1,count+1)))]
    assert len(evaluate(rule(kind,**config),data))==bool(count)


def test_duration_segmentation_and_gap():
    r=rule(threshold=2,minimum_duration_seconds=2)
    assert evaluate(r,frames([2,2],[0,1.999]))==[]
    events=evaluate(r,frames([2,3,4,0,3,3,3]))
    assert len(events)==2
    assert events[0]['condition_start_seconds']==0 and events[0]['trigger_seconds']==2
    assert events[0]['peak_value']==4 and events[0]['closure']=='condition_false'
    assert events[1]['condition_start_seconds']==4
    assert evaluate(r,frames([2,2,2],[0,1,3]))==[]
    assert len(evaluate(rule(threshold=2,minimum_duration_seconds=1),frames([2,2,2],[0,.3,1])))==1
    assert len(evaluate(rule(threshold=2),frames([2,2,2],[0,.3,3])))==2


def test_increase_actual_lookback_and_history():
    r=rule('SUDDEN_CROWD_INCREASE',increase_count=5,lookback_seconds=1)
    assert evaluate(r,frames([1,6],[0,.9]))==[]
    e=evaluate(r,frames([1,6],[0,1]))[0]
    assert e['baseline_seconds']==0 and e['trigger_value']==5
    assert evaluate(r,frames([1,5],[0,1]))==[]
    e=evaluate(r,frames([1,2,7],[0,.7,1.8]))
    assert e==[] # gap > one second breaks history
    e=evaluate(r,frames([1,2,7],[0,.7,1.6]))[0]
    assert e['baseline_seconds']==0 and e['trigger_value']==6


def test_order_duplicates_disabled():
    data=frames([1,2,3])
    assert evaluate(rule(threshold=1),data)==evaluate(rule(threshold=1),data[::-1])
    with pytest.raises(ValueError):evaluate(rule(threshold=1),data+[data[0]])
    r=rule(threshold=1);r.enabled=False
    assert evaluate(r,data)==[]


@pytest.mark.parametrize('config',[{'threshold':0},{'threshold':-1},{'threshold':1.5},{'threshold':True},
    {'threshold':float('nan')},{'threshold':float('inf')},{'threshold':'2'},
    {'threshold':1,'minimum_duration_seconds':-1},{'threshold':1,'minimum_duration_seconds':float('inf')},
    {'threshold':1,'maximum_gap_seconds':0},{'threshold':1,'other':2},{'threshold':1,'minimum_level':'HIGH'}])
def test_invalid_config(config):
    with pytest.raises(ValidationError):rule(**config)


@pytest.mark.parametrize('field,value',[('severity','DANGER'),('scope','ZONE'),('zone_id',uuid.uuid4()),('name',' ')])
def test_invalid_rule(field,value):
    data=rule(threshold=1).model_dump();data[field]=value
    with pytest.raises(ValidationError):RuleCreate.model_validate(data)


def test_invalid_increase():
    with pytest.raises(ValidationError):rule('SUDDEN_CROWD_INCREASE',increase_count=1,lookback_seconds=0)


def test_decimal_timestamp_boundaries():
    e=evaluate(rule(threshold=1,minimum_duration_seconds=1),frames([1,1,1],[1.3,1.8,2.3]))
    assert e[0]['trigger_seconds']==2.3
    e=evaluate(rule('SUDDEN_CROWD_INCREASE',increase_count=5,lookback_seconds=.2),frames([1,1,6],[.1,.2,.3]))
    assert e[0]['baseline_seconds']==.1


@pytest.mark.parametrize('values,expected',[([], 'NORMAL'),(['INFO'],'ELEVATED'),(['INFO','WARNING'],'HIGH'),(['WARNING','CRITICAL'],'CRITICAL')])
def test_risk(values,expected):assert operational_risk(values)==expected
