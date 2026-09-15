# Crowd Monitoring and Crowd Safety System

A privacy-conscious crowd-monitoring project. Phases 1–5 provide a React/TypeScript Sentinel Grid interface, JWT authentication, PostgreSQL persistence, protected video uploads, YOLO11 person detection, and anonymous within-video ByteTrack tracking.

## Quick start

Prerequisites: Docker Desktop, or Node 22+ and Python 3.12+ for local services (verified on Python 3.13).

Copy `.env.example` to `.env` and configure development credentials. Never commit secrets or media.

```powershell
docker compose up --build
docker compose exec backend alembic upgrade head
```

Open [Sentinel Grid](http://localhost:5173), register, sign in, and open **Video Analysis**. Upload an MP4, WebM, or MOV under 100 MB. Analysis is synchronous: leave the page open until completion. Results and preview are owner-protected; refreshing reloads persisted results. Delete removes the upload, preview, and database analysis.

See [development setup](docs/development.md), [architecture](docs/architecture.md), and [the real tracking verification procedure](docs/development.md#real-tracking-gate).

## Detection and anonymous tracking

The CV service runs official pretrained Ultralytics `yolo11n.pt` on CPU. It retains COCO person boxes only and feeds them to Ultralytics ByteTrack. Each video owns its tracker state and numerical ID allocator. IDs are temporary, session-local labels, never names or cross-video identities.

**distinct_track_ids != guaranteed unique real-world people**

Occlusion, missed detections, ID switches, fragmentation, leaving/re-entering, camera motion, crowded scenes, and sampling affect continuity. No tracking accuracy percentage has been established against labeled ground truth.

YOLO inference runs once on each frame needed by either detection reporting or tracking. Defaults: detection report every fifth frame at confidence 0.35; tracking every frame using person detections down to 0.1. ByteTrack associates high-confidence detections first, then uses lower-confidence detections to maintain existing tracks. New tracks require the high threshold (0.25). Unconfirmed/lost predictions do not count as active observed tracks.

Higher `TRACK_FRAME_STRIDE` reduces CPU work but weakens continuity. Skipped frames are **not tracked**, and trajectories connect observations across gaps. `TRACK_BUFFER` counts processed tracking frames. Bounding boxes use pixels; trajectories use normalized bounding-box centers, with top-left origin. No camera calibration, physical distance, or speed is inferred.

## Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| YOLO_MODEL | yolo11n.pt | Official pretrained detector |
| YOLO_CONFIDENCE_THRESHOLD | 0.35 | Detection reporting threshold |
| YOLO_IMAGE_SIZE | 640 | Inference size |
| YOLO_FRAME_STRIDE | 5 | Detection reporting stride |
| TRACKER_TYPE | bytetrack | Only supported tracker |
| TRACK_FRAME_STRIDE | 1 | Tracking processing stride |
| TRACK_HIGH_THRESHOLD | 0.25 | First association and new-track threshold |
| TRACK_LOW_THRESHOLD | 0.1 | Low-confidence person retention for association |
| TRACK_MATCH_THRESHOLD | 0.8 | ByteTrack assignment cost threshold |
| TRACK_BUFFER | 30 | Lost-track retention in processed tracking frames |
| CV_ANALYSIS_TIMEOUT_SECONDS | 600 | Backend CV request timeout |

Thresholds are finite values in [0,1], with low < high; strides and buffer must be positive. See exact validation bounds in the CV configuration schema. Score fusion is enabled; appearance embeddings and re-identification are absent.

## Stored results and UI

PostgreSQL stores the existing detection summary and frames plus a nullable versioned `tracking_analysis` JSON column. Tracking includes per-frame active boxes/IDs, per-track histories and normalized trajectories, processed-frame counts, maximum/average active tracks, distinct IDs, and observation lengths. Old Phase 4 videos remain readable with tracking unavailable until a new upload is analyzed.

The UI displays detection and tracking separately, an active-track timeline, selectable observed trajectories, and a JWT-authenticated JPEG preview labeled with real tracker IDs. It never sums frame counts into a unique-person estimate.

## Privacy and limits

No facial recognition, face embeddings, biometrics, demographic inference, identity database, re-identification, or cross-video matching. No density, heatmaps, zones, alerts, cameras, WebSockets, or training are implemented in Phase 5.

Uploaded footage and annotated previews remain sensitive local files even though track IDs are anonymous. They are retained until the owner deletes the video; there is no automatic retention job. Frame images are not stored in trajectories. The CV upload copy is deleted after analysis, including failures. Model weights, media, previews, logs, and secrets are excluded from Git; CV Docker context excludes runtime media and weights.

Processing remains synchronous and memory usage grows with observations; use short development clips. Process termination may leave a processing row requiring future worker reconciliation. Ordinary CV/validation/timeouts become safe failed states. There is no retry queue, automatic recovery worker, or large-video scalability guarantee. JWT localStorage is retained from Phase 2 and should be replaced with secure sessions before production. Dashboard values remain explicitly demo data.
