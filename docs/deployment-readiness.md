# Deployment readiness — Phase 13

Phase 14 must provide hosting, TLS, reverse proxy and operational controls. This
document records requirements; it does not deploy the application.

## Configuration

| Variable | Production requirement |
| --- | --- |
| `ENVIRONMENT` | Set `production`; startup rejects unsafe critical settings. |
| `DATABASE_URL` | Explicit `postgresql+psycopg://...`; dedicated credentials, URL-encode password special characters. |
| `JWT_SECRET_KEY` | Random secret, at least 32 characters; development/placeholders rejected. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"`. |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | HS256 only; positive lifetime (default 60 minutes). |
| `CORS_ORIGINS` | Comma-separated exact HTTPS frontend origins, no paths/trailing slashes/wildcards. Also governs WebSocket Origin validation. |
| `VITE_API_BASE_URL` | Public HTTPS backend URL at frontend build time; WebSocket URL derives WSS automatically. Never place secrets in `VITE_*`. |
| `CV_SERVICE_URL` | Explicit private CV HTTP(S) endpoint; CV is unauthenticated and must not be publicly exposed. |
| `VIDEO_STORAGE_PATH` | Writable persistent backend directory; Compose uses `/data/videos` in `video-storage`. |
| `MAX_UPLOAD_SIZE_BYTES` | Positive file limit (default 104857600); browser also caps uploads at 100 MiB. |
| `CV_ANALYSIS_TIMEOUT_SECONDS` | Positive, at most 3600; default 600. Align proxy timeouts with synchronous analysis. |
| `YOLO_MODEL`, `YOLO_*`, `TRACK_*`, `CROWD_*`, `LIVE_*` | See `.env.example`; retain verified defaults unless validated on intended hardware. |

For local backend commands, settings read `.env` in the working directory. Export
root `.env` values into the process environment or use Uvicorn `--env-file ../.env`.
Alembic needs the same environment. Vite reads frontend environment files or shell
variables, not the repository-root `.env` automatically.

Compose forwards authentication, upload, origins and model settings. Its database
URL uses `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` and internal `postgres`;
use `COMPOSE_DATABASE_URL` for a full URL with encoded credentials, and
`COMPOSE_CV_SERVICE_URL` to override the internal CV endpoint. Root `DATABASE_URL`
is for local backend commands. Change default PostgreSQL credentials before use.

## Startup, storage and networking

- Run `alembic upgrade head` from `backend` with its environment active. Expected
  single head: `20260926_09`. No Phase 13 schema changes. Back up existing data first.
- Start PostgreSQL, CV, then backend; backend Docker startup migrates before Uvicorn.
  Use exactly **one backend worker and one CV worker/replica**. Live state, tickets
  and tracker registries are in memory; restarts end live sessions. No load balancing
  across backend/CV replicas is supported.
- Compose is a **development launcher**: frontend runs Vite dev server. Phase 14
  must serve `npm run build` output (`frontend/dist`) with a production static server
  and SPA fallback to `index.html`; do not expose Vite dev/preview as production.
- Expose only HTTPS frontend/API. Proxy WebSocket Upgrade/Connection headers and
  `/api/v1/live/sessions/{id}/ws`; allow idle connections beyond the five-second
  heartbeat. Keep backend `--ws-max-size 1024 --ws-max-queue 4` settings.
- Require HTTPS/WSS for camera permissions and transport privacy. Keep PostgreSQL
  and CV on private networks (Compose host bindings are loopback). Configure trusted
  proxy forwarding deliberately; do not trust arbitrary clients' forwarding headers.
- Enforce request body limits at the proxy, including chunked requests and multipart
  overhead, plus upload timeouts and rate/concurrency limits for auth and inference.
  FastAPI parses/spools multipart before application file validation; the application
  alone is not an ingress upload quota or brute-force defense.
- Persist and back up PostgreSQL plus the video volume together. Restrict volume
  permissions; monitor free space and define retention and backup deletion policy.
  Uploads/previews persist until deletion; interrupted processes can leave orphan
  files or processing rows. Reconcile these manually during maintenance.
- CV CPU images need no GPU. Model loading is lazy; `/health` does not prove model
  readiness. Provision verified weights/cache and disk/network access before use.
  GPU deployment requires a separately validated image/runtime; do not assume the
  CPU image supports CUDA. Short clips are expected: synchronous results grow with
  observations; compressed file size does not bound duration or inference memory.

## Privacy, security and release limits

Live camera bytes are processed transiently, not written to storage. Persisted
tracks, camera/session metadata, uploads and previews still require access and
retention controls. Never log credentials, WebSocket tickets or frame payloads.
Use only authorized footage. Anonymous IDs are session-local, not unique people,
attendance or identity. Occupancy/concentration are image-space measurements,
not calibrated people/m²; operational risk is rule-derived, not danger prediction.

Ownership is the authorization boundary; role labels do not implement an admin
permission system. Registration is open. JWTs are in localStorage, expire, and
have no logout revocation; protect against XSS, shared-browser access and public
registration abuse. Configure CSP/security headers and ingress abuse controls in
Phase 14. The application is not a certified safety or emergency-response system.

Video lists return 20 records per `offset` page; alert lists return 200. UI shows
the latest page, with older records accessible by API. Existing camera/event/
incident lists also have caps. Analytics uses summary projections without N+1
queries but all-history aggregation still grows with stored history. No large-scale
capacity guarantee is made. Dashboard is demo data; Settings is unavailable.

## Pre-deployment checklist

- [ ] Configure production variables, random database/JWT credentials and private CV.
- [ ] Verify migration head on a clean database and backup/restore existing volumes.
- [ ] Pass backend/frontend tests, TypeScript, lint, frontend build and Compose config.
- [ ] Provide static hosting, HTTPS/WSS, SPA fallback and WebSocket proxy support.
- [ ] Configure body/rate/concurrency limits, timeouts, security headers and retention.
- [ ] Verify backend `/health` database availability and private CV `/health`.
- [ ] Smoke-test sign-in, ownership isolation, upload/delete, camera permission,
      WebSocket reconnect/REST fallback, analytics, incidents and CSV in the host environment.
- [ ] Validate model availability and practical CPU/GPU capacity; keep single workers.
- [ ] Confirm no secrets, footage, weights, reports, caches or logs enter Git/images.

Phase 9/10 real CV/live verification remains the baseline; Phase 13 does not change
inference or live processing and does not require another expensive YOLO run.

Local audit note: the existing CV virtual environment lacks the `opencv-python`
distribution required by Ultralytics (`pip check`), although headless OpenCV imports
and the health test pass. Both distributions are already pinned to `4.11.0.86` in
`cv-service/requirements.txt` and installed by its Dockerfile. Build/install from
that manifest for deployment and run `pip check`; do not copy the local virtual
environment. No dependency versions were changed during Phase 13.
