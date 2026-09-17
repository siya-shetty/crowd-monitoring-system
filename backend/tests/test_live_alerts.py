import pytest
from app.schemas.live import CameraRuleCreate
from app.services.live_alerts import LiveRuleState
from app.services.alert_engine import operational_risk, evaluate
from app.schemas.alerts import RuleCreate


def rule(**kw):
    return CameraRuleCreate.model_validate(dict(name='Count',scope='CAMERA',rule_type='CROWD_COUNT_ABOVE',configuration={'threshold':2},**kw)).model_dump(mode='json')


def obs(time,count):
    return dict(timestamp_seconds=time,observed_crowd_count=count,crowd_level='LOW',zones={})


def test_sustained_segmentation_gap_and_stop():
    r=rule();r['configuration'].update(minimum_duration_seconds=2,maximum_gap_seconds=1)
    state=LiveRuleState(r)
    for t in (0,1):
        assert state.step(t,obs(t,2),[])==[] and state.trigger is None
    state.step(2,obs(2,3),[]);assert state.trigger==(2,3,{})
    state.event_id='one'
    state.step(3,obs(3,4),[])
    closed=state.step(4,obs(4,0),[])
    assert closed[0][0]=='one' and closed[0][1]['last_observed_seconds']==3
    assert closed[0][1]['peak_value']==4 and state.trigger is None
    for t in (5,6,7):state.step(t,obs(t,2),[])
    assert state.close('session_stopped')[1]['closure']=='session_stopped'
    for t in (8,9,10):state.step(t,obs(t,2),[])
    assert state.step(13,obs(13,2),[])[0][1]['closure']=='observation_gap'
    assert state.trigger is None


@pytest.mark.parametrize('severity,risk',[('INFO','ELEVATED'),('WARNING','HIGH'),('CRITICAL','CRITICAL')])
def test_immediate_risk_and_session_isolation(severity,risk):
    a,b=LiveRuleState(rule(severity=severity)),LiveRuleState(rule(severity=severity))
    a.step(0,obs(0,2),[])
    assert a.trigger is not None and b.trigger is None
    assert operational_risk([severity])==risk
    assert operational_risk([])=='NORMAL'


def test_sudden_increase_baseline_gap_and_missing_history():
    r=CameraRuleCreate(name='Increase',scope='CAMERA',rule_type='SUDDEN_CROWD_INCREASE',configuration={'increase_count':2,'lookback_seconds':2.,'maximum_gap_seconds':1.}).model_dump(mode='json')
    state=LiveRuleState(r)
    recent=[]
    for t,c in ((0,0),(1,0),(2,2)):
        state.step(t,obs(t,c),recent);recent.append(obs(t,c))
    assert state.evidence()['baseline_count']==0
    assert state.step(5,obs(5,5),recent)[0][1]['closure']=='observation_gap'
    assert state.trigger is None


def test_live_matches_retrospective_intervals():
    r=rule();r['configuration']['minimum_duration_seconds']=1
    state=LiveRuleState(r);closed=[];frames=[]
    for t,c in enumerate([0,2,3,3,0,2,2,0]):
        observation=obs(t,c)
        closed.extend(e for _,e in state.step(t,observation,[]))
        frames.append(dict(frame_index=t,timestamp_seconds=t,observed_crowd_count=c,image_occupancy_ratio=0,crowd_concentration=0,crowd_level='LOW',crowd_count_delta=0,crowd_trend='stable'))
    historical=evaluate(RuleCreate.model_validate(r|{'scope':'VIDEO'}),frames)
    for a,b in zip(closed,historical,strict=True):
        for key in ('condition_start_seconds','trigger_seconds','last_observed_seconds','peak_value','closure'):
            assert a[key]==b[key]
