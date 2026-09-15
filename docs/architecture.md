# Architecture

## Current pipeline

```mermaid
flowchart LR
  F[React authenticated video UI] --> B[FastAPI ownership and lifecycle]
  B --> S[Local file storage]
  B -->|Uploaded bytes via HTTP| CV[CV video processor]
  CV --> D[Cached YOLO11 person detector]
  D --> T[Per-video ByteTrack adapter]
  T --> A[Typed frame results and history aggregation]
  A -->|Validated analysis contract| B
  B --> P[(PostgreSQL)]
  B -->|JWT protected JPEG and JSON| F
```

The backend owns authentication, upload limits, ownership, safe errors, storage, validation, and persistence. Only the CV service imports Ultralytics or performs tracking.

## Phase 5 boundaries

- `detection/detector.py`: cached lazy model, serialized CPU prediction calls, person-only filtering.
- `tracking/config.py`: validated small ByteTrack configuration surface.
- `tracking/tracker.py`: retained person boxes to Ultralytics Boxes, then BYTETracker. No image/appearance features are supplied.
- Each analysis constructs a new adapter. The pinned Ultralytics 8.4.152 `track_class` extension point supplies an STrack subclass with a closure-local allocator. This avoids upstream's global BaseTrack counter, including resets and interleaved videos. Actual tracker IDs are returned without relabeling.
- `video/processor.py`: chronological decoding, union of detection/tracking sample schedules, single inference per required frame, original frame indexes/timestamps, representative annotated JPEG, and unconditional capture release.
- `tracking/aggregation.py`: confirmed observed tracks, histories and metrics. Lost/predicted-only tracks are excluded from active counts.
- `tracking/schemas.py`: typed JSON contract. The backend mirrors this small deployment-independent schema; a regression test requires identical files.
- `backend/app/schemas/analysis.py`: rejects unknown internal fields, invalid numbers/IDs/boxes, incorrect counts, timing, incomplete frames, inconsistent histories and trajectories.
- `video_processing.py`: validate before committing results; rollback partial analysis and remove newly written preview on failure.

## Persistence decision

Migration `20260915_04` adds nullable `videos.tracking_analysis` JSON alongside existing Phase 4 JSON columns. Older migrations remain unchanged; old rows need no backfill. A single versioned document preserves atomic analysis and cascade-by-video deletion. This matches current detection storage and avoids a premature multi-table system. Future spatial queries or large histories can move to indexed JSONB or normalized observation tables through a new migration.

Per-frame objects contain frame index, timestamp, active count and tracked persons (ID, pixel box, confidence). A person's frame/time is inherited from its containing frame to avoid redundant payload. Histories include first/last frame and timestamp, observation count, average score, and timestamped normalized center points. These are image-space observations, not physical distances.

Tracking summaries retain tracker settings and carefully named metrics. Distinct IDs are not verified individuals. IDs may be nonconsecutive because unconfirmed tracks can be discarded before observation. ByteTrack buffer units are processed tracking frames, and no observations are synthesized for skipped frames.

## Operational boundaries

The detector is shared and locked, while motion state and ID allocation are per-video. Worker processes can use the same orchestration boundary later. Synchronous HTTP, JSON-in-row storage, whole-response transfer, and full trajectory rendering are intended for short clips. Future queue/recovery/retention work is separate; no Redis or Celery is added here.
