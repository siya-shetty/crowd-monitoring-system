# Retrospective operational alerts

Phase 8 evaluates stored crowd and polygon-zone observations in the backend.
It performs no image decoding, YOLO, ByteTrack, or CV HTTP requests. These are
user-configured operational review conditions, not predictions of accidents,
injury, stampedes, or a scientifically validated safety classification.

## Rules and configuration

| Type | Scope | Condition and configuration |
| --- | --- | --- |
| CROWD_COUNT_ABOVE | VIDEO | `observed_crowd_count >= threshold` |
| CROWD_LEVEL_AT_LEAST | VIDEO | stored crowd level >= `minimum_level` |
| SUDDEN_CROWD_INCREASE | VIDEO | current count minus lookback count >= `increase_count`; positive `lookback_seconds` |
| ZONE_COUNT_ABOVE | ZONE | `active_tracks_in_zone >= threshold` |
| ZONE_PRESENCE | ZONE | `active_tracks_in_zone >= minimum_presence_count`, default 1 |

Counts are strict integers >=1. Levels are ordered LOW, MODERATE, HIGH,
VERY_HIGH using persisted Phase 6 categories (default boundaries 5, 10, 20).
These categories are operational values, not universal safety standards.
All configurations accept finite `minimum_duration_seconds >= 0` (default 0)
and finite `maximum_gap_seconds > 0` (default 1). Numeric strings, booleans as
numbers, nonfinite numbers, irrelevant keys and unknown keys are rejected.
ZONE scope requires an owned same-video zone; VIDEO forbids a zone reference.
Severity is explicitly configured INFO, WARNING, or CRITICAL. Optional occupancy
and concentration rules are deferred. At most 100 rules are allowed per video.

## Time, continuity and segmentation

The pure evaluator validates individual persisted observations, sorts by actual
timestamp then frame index, and rejects duplicate timestamps or non-increasing
frame indexes. It does not assume a frame rate. A false condition resets the
qualifying interval. A gap strictly larger than the configured maximum resets
both the interval and sudden-increase history. Equality to the gap is allowed.
The default one-second gap is deliberately explicit; users must configure it
for their sampling cadence. It is not evidence of what occurred between samples.

Duration zero fires on the first qualifying observation. Otherwise, trigger time
is the first observation whose timestamp minus condition-start timestamp reaches
the required duration. A contiguous qualifying interval yields one event.
Comparisons allow an absolute 1e-9 second rounding tolerance, including lookback
selection, to avoid missing exact decimal boundaries due to binary floating point.
Condition-start time may precede trigger time. End time is the last qualifying
observation, never extrapolated to the first false sample or the video duration.
Closure records condition_false, observation_gap or end_of_analysis. All states
are HISTORICAL, including an interval still qualifying at the final observation.

Sudden increase uses binary search to select the most recent observation at or
before `current_timestamp - lookback_seconds`. No result is produced if history
is insufficient, crossed a discontinuity, or the baseline is more than the
configured maximum gap before the target. This is a count difference, not a flow
rate. Evidence retains the baseline timestamp/count and the current count.

## Persistence, ownership and re-evaluation

Migration `20260916_07` adds UUID `alert_rules` and `alert_events` tables.
Rule ownership follows the foreign-keyed video and its owner; no redundant owner
column can diverge. Configuration is JSON validated by a rule-specific Pydantic
model. Rules store name, description, type, scope, severity, enabled flag, optional
zone and creation/update timestamps. Events snapshot rule name, type, severity,
configuration and zone name with bounded typed evidence. No track histories,
frames, identities, filenames on disk or media bytes are copied into evidence.

All rule mutations acquire the same PostgreSQL video row lock as zone edits and
video deletion. Enabled create/update/explicit evaluation transactionally deletes
and rebuilds the rule's events; a unique (rule_id, condition_start_seconds)
constraint additionally prevents duplicate intervals. Rename-only updates rebuild
snapshots predictably. Event UUIDs may change; logical intervals remain identical.
The source series is loaded once per rule, evaluated in memory without per-frame
queries. Zone edits reuse their loaded analysis when rebuilding enabled rules.

Disabling retains existing history and prevents evaluations. Editing a disabled
rule also retains its prior snapshots until re-enabled. Deleting a rule preserves
events with nullable rule_id. Their historical risk contribution remains visible.
To remove an enabled rule's currently generated events through reconfiguration,
choose a non-triggering condition and save before disabling it.

Zone deletion returns 409 while any rule (including disabled rules) references
it. Delete those rules first; historical zone names remain in evidence and zone_id
becomes null. Editing/deactivating a zone rebuilds enabled dependent rules from
the refreshed stored zone series; inactive zones have no qualifying measurements.
Video deletion removes rules first, then cascades events and zones, as well as
the existing media and analysis cleanup. Missing earlier analysis yields no
events; no backfill inference is attempted.

Indexes cover rule video/zone/type/enabled and event video/rule/zone/severity/start.
Database checks enforce scope/type/zone combinations, severities and event time
ordering. API ownership is enforced on every video, rule and history operation.

## API and UI

All paths below have `/api/v1` prefix and require authentication.

| Method | Path |
| --- | --- |
| POST, GET | `/videos/{video_id}/alert-rules` |
| GET, PATCH, DELETE | `/videos/{video_id}/alert-rules/{rule_id}` |
| POST | `/videos/{video_id}/alert-rules/{rule_id}/evaluate` |
| GET | `/videos/{video_id}/alerts` |
| GET | `/videos/{video_id}/alerts/{alert_id}` |
| GET | `/videos/{video_id}/alert-summary` |
| GET | `/alerts` |

PATCH merges supplied rule fields, then validates the complete rule. A supplied
configuration replaces the entire configuration; omitted defaults are restored.
Video history accepts severity, rule_type, zone_id and rule_id filters; global
history accepts severity and rule_type. Global queries always join owned videos.

The video page includes dynamic rule fields, automatic scope, zone selection,
natural-language preview, create/edit/toggle/delete controls, event counts,
severity distribution and expandable evidence. Use Refresh alerts and zones after
editing spatial zones on the same page. Global `/alerts` shows video names and
historical evidence, including deleted-rule history. Both lists offer filters.
Dashboard metrics remain explicitly labeled demo data; they are not live risk.

## Operational risk

Maximum historical operational risk is derived only from persisted event severity:
no events -> NORMAL; INFO -> ELEVATED; WARNING -> HIGH; CRITICAL -> CRITICAL.
The highest severity wins. Disabled and deleted-rule history still contributes.
The summary includes total events, counts by severity/type, earliest trigger time,
configured rule count and enabled rule count. No weighted numeric score or risk
timeline is implemented. NORMAL means no generated events, not a safety finding.

## Limitations and privacy

Detection errors, occlusion, tracking fragmentation and ID switches affect alerts.
Counts describe simultaneous anonymous observed tracks, not attendance. Zone
membership uses image-space bottom-center foot-point approximation; perspective
distortion remains and there is no physical density or camera calibration.
Duration is supported by discrete observations and the stated gap policy only.
Thresholds and severities express user priorities, not validated danger levels.

Uploaded-video evaluation is retrospective; the system is not live monitoring.
No notifications, WebSockets, camera sources, incident assignments, predictive
models, facial recognition, biometrics, demographics, or cross-video identity are
introduced. History persists until video deletion; there is no timed retention job.
Full JSON analysis and unpaginated history are appropriate for short development
clips, not an established large-video scalability guarantee.

## Verification

Run backend pytest, frontend Vitest/lint/build and CV regression tests following
development.md. Alert tests include boundary conditions, duration resets, irregular
timestamps, gaps, level ordering, increase baselines, scope/configuration validation,
event segmentation, severity mapping, ownership, history preservation, zone edits,
cleanup, migration round trip and repeated evaluation. The lifecycle test replaces
both the backend analysis entry point and CV HTTP call with functions that raise;
all subsequent alert mutations must succeed without inference.

Real verification uses an ignored person-containing clip, then chooses thresholds
from measured observations. Verify triggering and non-triggering video/zone rules,
duration evidence, risk changes, refresh persistence, and cleanup in the browser.
Never commit downloaded clips, weights, generated previews or verification output.
