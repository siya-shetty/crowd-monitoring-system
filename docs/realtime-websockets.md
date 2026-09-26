# Phase 10: real-time monitoring transport

REST remains authoritative for camera configuration, session start/stop, frame
ingestion, history and recovery. The existing CV worker performs YOLO11 and
session-local ByteTrack once for each accepted frame. After persistence, the
backend publishes aggregate state to session-specific subscriber mailboxes.
Opening or reconnecting a socket never calls CV. Disconnecting a dashboard does
not stop a session. The existing local-preview capture lifecycle is unchanged.

## Endpoints and authentication

`POST /api/v1/live/sessions/{session_id}/ws-ticket` requires the existing Bearer
access token. Missing authentication returns 401; foreign and nonexistent sessions
both return 404. The response has `Cache-Control: no-store` and contains `ticket`
and `expires_in: 30`.

`WS /api/v1/live/sessions/{session_id}/ws` accepts an allowed Origin, then requires
the ticket as its first text message within five seconds. Until authentication
finishes it sends no session information. Invalid credentials, wrong session,
expired/reused tickets, inactive/deleted users and ownership failures close with
1008. Origin rejection occurs before acceptance. Stopped/failed sessions accept an
owned ticket, send terminal state, then close normally.

Tickets are 256-bit cryptographically random opaque capabilities, bound in memory
to a user and session. They expire using monotonic time and are consumed exactly
once, even on a wrong-session attempt. They are not JWTs and cannot authorize REST.
The bounded registry holds at most 256 tickets, with eight outstanding per user;
expired entries are purged on issuance. Nothing is persisted. Restart invalidates
all tickets. No access token or ticket appears in a socket URL, protocol header,
log statement or verification report. Do not enable WebSocket body/debug logging
at a proxy. Use TLS in production. Access-token expiry prevents acquiring another
ticket; established connections are session-scoped, with user activity and
ownership rechecked on each five-second refresh.

## Contract and ordering

Events have `version: 1`, `event`, `session_id`, `sequence`, `emitted_at`, `data`,
and optional `alert`. `data` is a typed aggregate state containing session status,
frame counts, last-frame time, stale flag, safe error summary, current metrics,
zone counts and at most 50 active/recent alerts (active alerts prioritized).
Alerts include ID, rule snapshot (ID/name/type/severity/scope/zone), evidence and
created/resolved timestamps. Metrics omit all individual tracks and image bytes.

Events are `session.snapshot`, `alert.triggered`, `alert.resolved`,
`session.stopped`, and `session.failed`. Initial connection and periodic freshness
refresh send current state. Every successfully processed frame publishes current
state and its real alert transitions. Stop/failure carries resolved alert state;
it does not invent a new alert condition. STARTING/RUNNING and stale/recovered
status are represented in snapshots, rather than artificial lifecycle events.

The locked process-wide allocator creates strictly increasing JavaScript-safe
integer sequences; therefore each session's subsequence increases, with gaps.
These are **not camera frame sequences**. Frame sequence remains inside metrics.
The allocator uses epoch microseconds plus a monotonic increment within a process.
Reconnect in the same process continues ordering. No cross-process ordering or
historical replay guarantee is offered. Restart reconciliation fails interrupted
sessions; it does not preserve tracker state or provide seamless failover.

## Delivery, backpressure and cleanup

Default cap: four subscribers per session, configurable with
`LIVE_WS_SUBSCRIBER_CAP` (1–16). Each connection has **one pending batch** holding
the latest state plus that frame's bounded alert transitions (at most 101 events).
Publishing only replaces the mailbox under a short thread lock; it never awaits
network I/O or schedules an unbounded series of event-loop callbacks. A batch
already being sent and one pending replacement are the maximum retained batches.
The sender checks every 50 ms and gives each send a two-second deadline.
Slow sends close with 1008. Replaced transition messages are not an audit log;
the latest snapshot restores active/recent state, and REST provides full history.
All subscribers to the same publish receive the same sequence numbers.

The route owns its sender loop and one receiver task. On disconnect, failure,
timeout or cancellation it cancels/joins the receiver, removes the subscriber,
clears its mailbox and removes empty rooms. Terminal state is sent before normal
1000 closure where delivery is possible; slow/unreachable clients recover by REST.

The only client messages are the initial ticket and literal `pong`. A small
`{"version":1,"event":"heartbeat"}` arrives every five seconds. More than 15
seconds without pong closes the connection. The browser has a 16-second receive
watchdog. Unexpected text/binary messages are rejected. Docker runs Uvicorn with
`--ws-max-size 1024 --ws-max-queue 4`; use these same flags for local servers.
Application checks are additional defenses, not substitutes for transport limits.
Production ingress should also limit unauthenticated connection rates.

## Dashboard and recovery

`frontend/src/services/liveSocket.ts` owns ticket acquisition, URL construction,
envelope validation, sequencing, heartbeat and reconnect. Invalid JSON or malformed
state cannot update the UI. Duplicate/older sequences are ignored. Backoff starts
at 0.5 seconds, doubles to eight seconds, with ±20% jitter. Fresh tickets are
acquired each attempt; success resets backoff. Intentional cleanup, terminal state,
or REST 401/403/404 stops retries. Authentication 401 uses the existing auth event.

The dashboard displays LIVE / RECONNECTING / DISCONNECTED separately from session
RUNNING / STALE / STOPPED / FAILED. Camera freshness uses Phase 9's threshold
(default ten seconds); five-second socket refreshes detect staleness without frames.
A connected socket is not proof of current camera observations. The page obtains
REST recovery state immediately and every five seconds while disconnected; healthy
streaming stops that polling. Terminal session state cannot be overwritten by an
older in-flight recovery response.

Local preview remains. Current observed crowd, crowd level, image occupancy,
image-space concentration, rule-derived operational risk, processed/dropped frames,
latency, zones and active/recent alert evidence update from socket state. A rolling
SVG count chart retains only 60 observations and deduplicates frame sequence across
heartbeat snapshots. Occupancy is shown numerically to avoid a second crowded chart.
Text health/risk labels, status announcements, SVG accessible description, visible
focus states and responsive cards support keyboard/screen-reader and narrow layouts.
Image occupancy and concentration are not physical people/m² or incident prediction.

## Deployment and privacy

No migration: Alembic head remains `20260916_08`. No database write is performed
merely to emit an event. All socket state/tickets are ephemeral. Use one backend
worker and one CV worker. Horizontal scaling requires session ownership/routing
and shared pub/sub such as Redis; the mailbox manager alone does not provide it.

`VITE_API_BASE_URL` is the same HTTP base as REST; the client converts HTTP to WS
and HTTPS to WSS and appends the socket path. Empty base supports same-origin.
Both `http://localhost:5173` and `http://127.0.0.1:5173` are default allowed Origins.
Set `CORS_ORIGINS` to exact deployed frontend origins; missing/foreign origins are
rejected, and `*` does not wildcard-match WebSocket origins. Compose uses direct
browser-to-backend ports. Production reverse proxies must forward WebSocket Upgrade
and Connection headers, preserve Origin, use HTTPS/WSS and allow idle timeouts
longer than the heartbeat cycle (for example 60 seconds). No deployment is included.

No raw-frame socket streaming, recordings, faces, biometric identifiers,
embeddings, re-identification, demographics or cross-session identities are added.
Only aggregate metrics and user-owned operational events are transmitted.
Phase 11 long-term/comparative analytics, narrative summaries and reporting remain
out of scope.

## Verification

Run backend `tests/test_websocket.py` and the complete backend/CV/frontend suites.
Socket tests cover authorization, single-use/expiry, origins, two subscribers,
initial/frame/final state, reconnect, no CV on subscription, bounded replacement,
an intentionally blocked sender, triggered/resolved alerts, stale state and failure.
Client/page tests cover validation, stale sequence rejection, fresh tickets,
reconnect/intentional stop, heartbeat, chart, alerts, camera freshness and recovery.

With local PostgreSQL and services on 8010/8011, run:

```powershell
# cv-service directory; use existing ignored verification video
.venv/Scripts/python.exe scripts/verify_websockets.py ../storage/phase5-verification/source.avi
```

This permanent verification script prints aggregate evidence and removes its
cameras/sessions. It uses real sequential frames, not a physical webcam. It tests
two real subscribers, disconnect/reconnect, an isolated second session, delayed
reading, real alert triggering and closure, and anonymous track continuity.
An unread real network client may still fit in OS buffers: mailbox replacement and
timeout claims are separately established with the deterministic blocked-sender test.
It does not claim that a short delayed-reader run saturates TCP buffers.
