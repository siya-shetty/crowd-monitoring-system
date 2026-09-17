"""Incremental Phase 8 intervals with constant state per rule and bounded lookback."""
from app.schemas.crowd import LEVELS
from app.services.alert_engine import condition_details


class LiveRuleState:
    def __init__(self, rule):
        self.rule = rule
        self.start = self.last = self.peak = self.trigger = self.previous = None
        self.event_id = None

    def close(self, reason):
        evidence = self.evidence(reason) if self.trigger is not None else None
        event_id = self.event_id
        self.start = self.last = self.peak = self.trigger = self.event_id = None
        return (event_id, evidence) if evidence else None

    def evidence(self, reason=None):
        cfg = self.rule['configuration']
        metric, threshold = condition_details(self.rule)
        return dict(metric=metric, operator='>=', threshold=threshold,
            trigger_value=self.trigger[1], peak_value=self.peak, condition_start_seconds=self.start,
            trigger_seconds=self.trigger[0], last_observed_seconds=self.last,
            minimum_duration_seconds=cfg['minimum_duration_seconds'], maximum_gap_seconds=cfg['maximum_gap_seconds'],
            observed_duration_seconds=self.last-self.start, closure=reason, **self.trigger[2])

    def step(self, time, observation, recent):
        cfg = self.rule['configuration']
        closed = []
        if self.previous is not None and time-self.previous > cfg['maximum_gap_seconds']+1e-9:
            result = self.close('observation_gap')
            if result:
                closed.append(result)
        self.previous = time
        metric, threshold = condition_details(self.rule)
        extra = {}
        if self.rule['scope'] == 'ZONE':
            zone = observation['zones'].get(str(self.rule['zone_id']))
            value = zone['active_tracks_in_zone'] if zone else None
            extra['zone_name'] = zone['name'] if zone else None
        elif metric == 'crowd_count_increase':
            target = time-cfg['lookback_seconds']
            baseline = next((f for f in reversed(recent) if f['timestamp_seconds'] <= target+1e-9), None)
            # A missing/gapped baseline must not invent a count delta.
            window = [f for f in recent if baseline and f['timestamp_seconds'] >= baseline['timestamp_seconds']]
            times = [f['timestamp_seconds'] for f in window]+[time]
            valid = baseline and target-baseline['timestamp_seconds'] <= cfg['maximum_gap_seconds']+1e-9
            valid = valid and all(b-a <= cfg['maximum_gap_seconds']+1e-9 for a,b in zip(times,times[1:]))
            value = observation['observed_crowd_count']-baseline['observed_crowd_count'] if valid else None
            if valid:
                extra = dict(baseline_seconds=baseline['timestamp_seconds'], baseline_count=baseline['observed_crowd_count'], current_count=observation['observed_crowd_count'])
        else:
            value = observation[metric]
        compare = lambda v: LEVELS.index(v) if isinstance(v, str) else v
        if not self.rule['enabled'] or value is None or compare(value) < compare(threshold):
            result = self.close('condition_false')
            if result:
                closed.append(result)
        else:
            if self.start is None:
                self.start, self.peak = time, value
            self.last = time
            if compare(value) > compare(self.peak):
                self.peak = value
            if self.trigger is None and time-self.start >= cfg['minimum_duration_seconds']-1e-9:
                self.trigger = (time, value, extra)
        return closed
