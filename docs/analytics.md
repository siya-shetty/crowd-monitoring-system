# Analytics and session summaries

Phase 11 reads existing persisted data. No migration, inference, new dependency,
external AI, media reads, or change to the Phase 10 WebSocket pipeline.

## API and access

- `GET /api/v1/analytics?range=7d|30d|all` (default `30d`).
- `GET /api/v1/analytics/sessions/{session_id}`: historical or active session detail.

Both require an active authenticated user and return `Cache-Control: no-store`.
Source queries are owner-scoped; foreign/missing session IDs return 404.

## Time and formulas

Rolling UTC ranges end at request time, inclusive of both endpoints. Videos use
upload (`created_at`), sessions use `started_at`. Their full stored results and
alerts are included, even if alerts were created later. This is a source-cohort
filter, not an alert-occurrence or video-capture-time filter. Detail covers the
whole session independently of dashboard range.

Video and live measurements remain separate:

- Analyzed videos have a persisted crowd summary. Video status counts also include
  records without crowd results. All selected live statuses are counted; STOPPED
  means completed, FAILED is separate, and active sessions have partial metrics.
- Average observed crowd count = sum(source average * processed frames) / sum of
  processed frames with that metric. Video weight is `processed_crowd_frames`;
  live weight is `processed_frame_count`. No observations returns null, not zero.
- Peak count = maximum stored source peak with positive processed frame count.
- Video image occupancy and image-space concentration use frame-weighted means.
  Live historical image averages/peaks were not persisted and are unavailable;
  the last frame cannot substitute for a session average or peak.
- Video crowd levels count processed frames; live levels count sessions by stored
  maximum level. Threshold configurations may differ: these are recorded labels,
  not universal safety thresholds.
- Alert totals and severity/type breakdowns count stored events, including resolved
  events. Video and live events can be counted together as events, not observations.
- Video maximum rule-derived operational risk uses the existing severity mapping:
  no events NORMAL, INFO ELEVATED, WARNING HIGH, CRITICAL CRITICAL. Live maximum
  risk uses the stored session summary; missing risk is excluded.
- Daily history uses UTC upload/start dates and frame-weighted averages. Peak cohort
  dates select the largest peak, earliest date on ties. These are not capture-time
  busy hours or continuous measurements. The chart shows the latest 90 populated
  dates; totals and peak selection cover the entire range.
- Video zones expose stored average/peak simultaneous anonymous tracks. Live zone
  names and peaks come from session snapshots. Overlapping zones are not summed.

## Deterministic session summaries

Detail includes start/end, nonnegative duration (end minus start), processed/dropped
frames, count average/peak, maximum crowd level/risk, final stored risk, zone peaks,
and alert breakdown/history. Existing closure logic resets final risk to NORMAL;
this is not the last pre-stop observed risk.

STOPPED/FAILED sessions receive template text: duration to one decimal minute,
peak count when available, severity counts in fixed order, and maximum stored risk.
Failures add an incomplete-observations sentence. Active sessions have no completed
summary. Identical stored inputs produce identical text, without network calls or
LLMs. Missing metrics are never backfilled or fabricated.

## Performance, limitations and privacy

Overview uses five batched queries; detail uses two, without N+1 queries. JSON
summary projection excludes video frame arrays and live snapshot tracks. Responses
are limited to 30 recent sessions, 50 video zones, 90 populated history dates and
100 latest detail alerts. Breakdowns remain complete. Aggregation scans matching
summaries and event rows in memory; all-time cost grows with retained history.
Camera names reflect current configuration; zone names retain session snapshots.
No historical live timeline or peak-image statistics can be reconstructed.

No footage, images, track IDs, trajectories, credentials or storage paths are
returned. Anonymous tracks are not visitors, attendance or unique people. Image
occupancy/concentration are image-space proxies, not calibrated physical density.
Rule-derived operational risk is descriptive, not an incident probability or safety
prediction. Deleting source data removes its analytics; video rule re-evaluation
can change historical alerts. There is no additional retention store.

## Verification

Backend fixtures cover authentication, ownership, empty/populated results, weighted
calculations, time ranges, alert/risk aggregation, summaries, privacy and limits
without CV. Frontend tests cover loading, range selection, charts/metrics,
summaries/drill-down, empty and error states.
