# Live camera monitoring (Phase 9)

## Architecture and scope

`/live` and `/cameras` support browser cameras. The browser obtains a local
`getUserMedia({video: ..., audio: false})` stream with explicit permission. HTTPS
is required except on localhost. A browser camera belongs to the user's device;
server `VideoCapture(0)` cannot access a remote user's camera. Server webcams and
RTSP are deferred. No WebSockets, SSE, push notifications, or Phase 10 dashboard
streaming are implemented. The existing dashboard remains clearly marked demo data.

The browser captures an aspect-preserving JPEG up to 960×540 into a canvas and
sends binary HTTP requests to the authenticated backend. The backend owns camera
configuration, authorization, session persistence, zone geometry, and incremental
alerts. A private CV worker owns each session's independent `PersonTracker`
(ByteTrack), using the existing lazy-loaded CPU YOLO11 detector. IDs are temporary,
session-local anonymous labels, not identities or unique visitors. Tracking resets
on a new session. The model is not loaded per frame.

## Lifecycle and REST API

All public endpoints below are under `/api/v1` and require a valid active user.
Ownership is enforced for every camera, session, zone, rule, and event request.

| Endpoint | Behavior |
| --- | --- |
| `GET /live/config` | Capture settings |
| `POST, GET /cameras` | Register/list browser cameras |
| `GET, PATCH, DELETE /cameras/{id}` | Camera configuration; deletion cascades history |
| `GET, POST /cameras/{id}/zones` | Camera-specific polygons |
| `PATCH, DELETE /cameras/{id}/zones/{zone}` | Edit/delete a zone |
| `GET, POST /cameras/{id}/alert-rules` | Camera rule configuration |
| `PUT, DELETE /cameras/{id}/alert-rules/{rule}` | Replace/delete a rule |
| `POST /cameras/{id}/sessions` | Start monitoring |
| `GET /cameras/{id}/sessions` | Latest 100 sessions |
| `POST /live/sessions/{id}/frames` | Binary JPEG/WebP; sequence and timestamp query parameters |
| `GET /live/sessions/{id}` | Persisted snapshot, stale flag, bounded recent aggregate observations |
| `GET /live/sessions/{id}/alerts?offset=0` | Persisted events, 100 per page |
| `POST /live/sessions/{id}/stop` | Idempotent stop |
| `DELETE /live/sessions/{id}` | Delete stopped/failed session and its events |

Camera records contain UUID, owner, name, description, source type, empty browser
source configuration, enabled flag, and timestamps. Browser device identifiers and
credentials are not stored. Session records contain owner/camera, lifecycle
timestamps, status, processed/dropped counters, safe error, latest snapshot, and
summary. States are STARTING → RUNNING → STOPPING → STOPPED, or FAILED.

A PostgreSQL partial unique index enforces one STARTING/RUNNING/STOPPING session
per camera, with row locking for concurrent starts/configuration changes. A disabled
camera cannot start. Deletion is blocked while a session is active. Disabling a
camera does not stop an existing session; use Stop Monitoring explicitly.

Start snapshots at most 50 zones and 50 rules into the session. Edits apply to the
next session, never silently change an active interval. The worker reserves state
at start and creates the dimension-specific tracker on the first valid frame.
Stop serializes with in-flight processing, rejects further frames, closes active
events with `session_stopped`, persists the summary, and removes tracker/recent
state. No pending image queue exists. Repeated stop does not alter final history.

## Validation, time, and backpressure

Each frame uses a positive increasing `sequence` and `capture_timestamp` in Unix
seconds. Duplicate/out-of-order sequences or non-increasing capture timestamps
return 409; invalid frames do not advance state. Capture time must be within 60
seconds of server wall time. It is recorded for diagnostics, not trusted for alert
duration. Server monotonic elapsed processing observations drive sustained alerts
and gaps; received/processed UTC timestamps are included in snapshots.

Frame bodies are streamed with a 512 KiB default limit and a 10-second upload
deadline. Only JPEG/WebP content types are allowed. The CV worker checks actual
encoded format and dimensions using Pillow before OpenCV decoding; dimensions
must be at least 16 pixels per side, at most 1920 per side, and at most 921,600
pixels by default. Resolution must remain fixed within a session. Malformed and
oversized frames are rejected before inference and do not normally end a session.

The browser sends one frame, awaits completion, then waits `1 / LIVE_TARGET_FPS`
before capturing a fresh frame. No overlapping uploads or saved backlog. The
backend admits one in-flight request per session and rejects excess/too-frequent
frames with 429, incrementing the dropped count. The CV worker admits one live
inference across sessions and rejects contention with 429. There are zero queued
pending frames. Rejected frames are never retried as stale captures. The default
3 FPS is an ingestion ceiling, not a measured throughput guarantee; inference and
network time further reduce actual cadence. Hidden tabs pause capture and browsers
can throttle timers. Normal REST snapshot polling is once per second and does not
overlap itself.

## Measurements and alerts

The existing Phase 6 functions compute simultaneous active-track count, exact
rectangle-union image occupancy, and normalized image-space concentration.
Configured count categories are unchanged. Delta compares adjacent processed
observations; trend uses the same OLS change over the last ten observations and
does not estimate motion, forecast danger, or use physical people/m².

Camera zones use the Phase 7 polygon validation, clipped bottom-center foot point,
and inclusive boundary semantics. Overlapping zones are allowed. Each active zone
reports current count and anonymous track IDs.

Camera rules use CAMERA or ZONE scope and the Phase 8 configuration validation,
metric/threshold selection, severity, and risk mapping. Supported types are
CROWD_COUNT_ABOVE, CROWD_LEVEL_AT_LEAST, SUDDEN_CROWD_INCREASE, ZONE_COUNT_ABOVE,
and ZONE_PRESENCE. As in Phase 8, thresholds are inclusive (`>=`).

Incremental state retains the condition start, last qualifying observation, peak,
trigger, and current event ID per rule. Sustained truth creates one event, not one
per frame. False conditions or excessive observation gaps close the interval at
its last qualifying observation. A subsequent interval creates a separate event.
Sudden increase selects a baseline at/before the lookback target, with the same
maximum-gap semantics; missing bounded history cannot invent a baseline. Live
lookback is limited to 60 seconds and is also constrained by the configured
observation buffer. Increase buffer size if a high ingestion rate shortens usable
history. Events retain rule/zone context, severity, condition/trigger/last-observed
elapsed times, resolution UTC time, evidence, and closure reason.

Current rule-derived operational risk is NORMAL without active triggered events,
ELEVATED for INFO, HIGH for WARNING, and CRITICAL for CRITICAL. It is not predictive
danger. A stale snapshot describes the last observation, not current conditions.

## Persistence, failure, and deployment

Each successfully processed frame updates one session JSON snapshot and running
summary; it does not insert a frame-history row. Only the latest snapshot contains
track boxes. The in-memory recent deque holds at most 300 aggregate observations,
not frame images or trajectories. Summaries retain max/average count, maximum
level/risk, event count, per-zone peaks, mean processing time, duration, counts,
configuration snapshots, and closure/failure information. Events persist separately
until the session/camera is explicitly deleted. There is no automatic historical
retention scheduler in this phase; operators must set deployment retention policy
and delete expired history through the authenticated APIs.

After 10 seconds without successful frames, the snapshot reports `is_stale`.
No automatic stale-session notification is sent. The CV worker releases idle
tracker state after 120 seconds (checked every ten seconds). A later frame detects
lost worker state and fails the DB session; tracking never silently resumes with
new IDs. Backend startup reconciles prior active sessions as FAILED with
`backend_restarted`, closes open events, and attempts worker cleanup. Unexpected
inference/transport errors fail closed on the first error because tracker mutation
cannot safely be rolled back; invalid input is handled separately. Safe error
summaries contain no traceback. An unreachable worker is reclaimed by idle expiry.

Use exactly one backend process and one CV process for Phase 9. Multiple processes,
reloads, and rolling deployments need session routing/worker ownership and coordinated
recovery before production horizontal scaling is supported. Backend startup recovery
assumes exclusive ownership. Default capacity is eight sessions, not eight parallel
inferences. Uploaded-video jobs share the process model lock and may increase latency;
schedule them separately when latency matters.

Compose binds the development CV port to loopback. Production must omit its host
port entirely and keep CV APIs on a private trusted network; they are internal
orchestration endpoints, not browser-authorized endpoints. Configure HTTPS,
authentication secrets, request limits, and origin allowlists for deployment.

## Privacy and verification

Live images exist transiently in memory. No raw camera images, recordings,
face storage, embeddings, re-identification, demographics, or cross-session identity
are implemented. No debug image capture is enabled. Protect aggregate history and
configuration as user-owned data. Do not commit model weights or verification media.

Run targeted backend `test_live*` and CV `test_live.py`, plus frontend LivePage
tests. Migration `20260916_08` follows `20260916_07`; older migrations are unchanged.
Migration tests exercise upgrade/downgrade/re-upgrade in an isolated transactional
schema. `cv-service/scripts/verify_live.py` runs actual YOLO/ByteTrack on sequential
frames decoded from the existing person-containing verification video, through
the authenticated live endpoint. It checks continuity, real burst rejection,
active/quiet zones, sustained triggering/non-triggering rules, risk, stop, persistence,
and released buffers. This is **real-frame live transport simulation**, not physical
webcam verification. Write its report only to ignored storage and remove it before
committing. Physical camera availability is a separate manual gate when supported.

### Verified development results (2026-09-17)

The real-frame transport gate processed 21 frames at 768×576 using `yolo11n.pt`
on CPU. IDs 1 and 2 appeared in all 20 sequential observations; ID 3 appeared in
19. The active zone peaked at five tracks and the quiet zone at zero. A 12-request
burst produced one accepted frame and eleven counted HTTP 429 drops. The count
rule sustained beyond its one-second requirement, the non-triggering rule remained
silent, zone presence triggered, and current operational risk was HIGH. Both open
events closed on stop. Repeated stop preserved the summary; refresh preserved
history; recent buffers were empty and a direct CV frame probe returned 410 after
stop, confirming worker state removal.

Median worker processing was 118.25 ms; mean was 1,242.06 ms including cold model
startup in the short sample. Inverse median is about 8.46 processing frames/second,
not an end-to-end sustained throughput claim. Configured browser target remains
3 FPS, with request completion plus pacing determining actual cadence. These
measurements do not establish performance for other hardware, camera scenes, or
concurrent workloads. Physical webcam capture was not verified in the available
automation environment; the real-frame fallback and media-lifecycle tests were used.
