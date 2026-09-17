"""Pure interval evaluation. No database, media, network or inference imports."""
from bisect import bisect_right
from math import isclose
from app.schemas.alerts import RuleCreate, Evidence
from app.schemas.crowd import CrowdFrame, LEVELS
from app.schemas.spatial import ZoneFrame


def operational_risk(severities):
    rank = {'INFO': 1, 'WARNING': 2, 'CRITICAL': 3}
    return ('NORMAL', 'ELEVATED', 'HIGH', 'CRITICAL')[max((rank[s] for s in severities), default=0)]


def condition_details(rule):
    """Canonical metric/threshold selection shared by finite and live intervals."""
    kind, cfg = rule['rule_type'], rule['configuration']
    metric = ('active_tracks_in_zone' if rule['scope'] == 'ZONE' else
        'crowd_level' if kind == 'CROWD_LEVEL_AT_LEAST' else
        'crowd_count_increase' if kind == 'SUDDEN_CROWD_INCREASE' else 'observed_crowd_count')
    threshold = cfg.get('threshold', cfg.get('minimum_presence_count', cfg.get('increase_count', cfg.get('minimum_level'))))
    return metric, threshold


def evaluate(rule: RuleCreate, raw_frames: list[dict], zone_name=None):
    """Sort input, reject ambiguous timestamps, and emit bounded historical intervals.

    End is the last known qualifying observation, never extrapolated to a false
    sample or EOF. Lookback chooses at/before target within maximum_gap_seconds.
    """
    schema = ZoneFrame if rule.scope == 'ZONE' else CrowdFrame
    frames = sorted((schema.model_validate(f) for f in raw_frames), key=lambda f: (f.timestamp_seconds, f.frame_index))
    if any(b.timestamp_seconds <= a.timestamp_seconds or b.frame_index <= a.frame_index for a, b in zip(frames, frames[1:])):
        raise ValueError('Ambiguous observation timestamps or frame indexes')
    if not rule.enabled:
        return []
    cfg = rule.configuration
    gap = cfg['maximum_gap_seconds']
    duration = cfg['minimum_duration_seconds']
    kind = rule.rule_type
    metric, threshold = condition_details(rule.model_dump())
    compare = lambda value: LEVELS.index(value) if isinstance(value, str) else value
    times = [f.timestamp_seconds for f in frames]
    events = []
    start = last = peak = trigger = None
    segment_start = 0

    def close(reason):
        if trigger is not None:
            events.append(Evidence(metric=metric, threshold=threshold, trigger_value=trigger[1], peak_value=peak,
                condition_start_seconds=start, trigger_seconds=trigger[0], last_observed_seconds=last,
                minimum_duration_seconds=duration, maximum_gap_seconds=gap,
                observed_duration_seconds=last-start, zone_name=zone_name, closure=reason, **trigger[2]).model_dump())

    for i, frame in enumerate(frames):
        time = times[i]
        if i and time-times[i-1] > gap and not isclose(time-times[i-1], gap, rel_tol=0, abs_tol=1e-9):
            close('observation_gap')
            start = last = peak = trigger = None
            segment_start = i
        extra = {}
        if kind == 'SUDDEN_CROWD_INCREASE':
            target = time-cfg['lookback_seconds']
            index = bisect_right(times, target+1e-9, hi=i)-1
            if index < segment_start or target-times[index] > gap+1e-9:
                value = None
            else:
                baseline = frames[index]
                value = frame.observed_crowd_count-baseline.observed_crowd_count
                extra = dict(baseline_seconds=times[index], baseline_count=baseline.observed_crowd_count, current_count=frame.observed_crowd_count)
        else:
            value = getattr(frame, metric)
        if value is None or compare(value) < compare(threshold):
            close('condition_false')
            start = last = peak = trigger = None
            continue
        if start is None:
            start = time
            peak = value
        last = time
        if compare(value) > compare(peak):
            peak = value
        if trigger is None and (time-start >= duration or isclose(time-start, duration, rel_tol=0, abs_tol=1e-9)):
            trigger = (time, value, extra)
    close('end_of_analysis')
    return events
