"""Read-only analytics of persisted aggregates, never tracker identities or media."""
from collections import Counter
from datetime import timezone

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def breakdown(events):
    return dict(total=len(events), by_severity=dict(Counter(e.severity for e in events)),
                by_type=dict(Counter(e.rule_type if hasattr(e, 'rule_type') else
                                     e.rule_snapshot.get('rule_type', 'UNKNOWN') for e in events)))


def session_data(session, camera_name, alerts):
    summary = session.summary or {}
    latest = session.latest_snapshot or {}
    duration = max(0, (utc(session.stopped_at)-utc(session.started_at)).total_seconds()) if session.stopped_at else None
    zones = [{ 'id': z['id'], 'name': z['name'],
               'peak_count': summary.get('zone_peak_counts', {}).get(z['id']) }
             for z in summary.get('zones', [])]
    risk = summary.get('maximum_operational_risk')
    result = dict(id=str(session.id), camera_name=camera_name, status=session.status,
        started_at=session.started_at, stopped_at=session.stopped_at, duration_seconds=duration,
        processed_frames=session.processed_frame_count, dropped_frames=session.dropped_frame_count,
        average_count=summary.get('average_observed_crowd_count'),
        peak_count=summary.get('maximum_observed_crowd_count'),
        maximum_crowd_level=summary.get('maximum_crowd_level'), maximum_operational_risk=risk,
        final_operational_risk=latest.get('current_operational_risk'),
        peak_image_occupancy=None, peak_image_space_concentration=None,
        zones=zones, alerts=breakdown(alerts), summary=None)
    if session.status in ('STOPPED', 'FAILED'):
        parts = [f"Monitoring ran for {duration / 60:.1f} minutes." if duration is not None else 'Monitoring duration is unavailable.']
        if result['peak_count'] is not None:
            parts.append(f"Peak observed crowd count was {result['peak_count']}.")
        else:
            parts.append('No crowd observations were stored.')
        counts = result['alerts']['by_severity']
        if alerts:
            parts.append('Recorded alerts: ' + ', '.join(f'{counts[s]} {s.lower()}' for s in ('INFO', 'WARNING', 'CRITICAL') if counts.get(s)) + '.')
        else:
            parts.append('No alerts were recorded.')
        if risk is not None:
            parts.append(f'Maximum rule-derived operational risk was {risk}.')
        if session.status == 'FAILED':
            parts.append('The session ended with a failure; observations may be incomplete.')
        result['summary'] = ' '.join(parts)
    return result


def aggregate(items):
    """Each item carries its own count of processed observations as weight."""
    def average(key):
        available = [(s[key], n) for s, n in items if n > 0 and s.get(key) is not None]
        total = sum(n for _, n in available)
        return sum(v*n for v, n in available)/total if total else None
    peaks = [s['maximum_observed_crowd_count'] for s, n in items if n > 0 and s.get('maximum_observed_crowd_count') is not None]
    return dict(observations=sum(n for _, n in items), average_count=average('average_observed_crowd_count'),
        peak_count=max(peaks, default=None), average_image_occupancy=average('average_image_occupancy'),
        average_image_space_concentration=average('average_crowd_concentration'))
