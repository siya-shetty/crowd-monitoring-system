# Phase 7: observation heatmaps and monitoring zones

Spatial analysis uses only anonymous tracking geometry. The backend is the
canonical spatial-math owner: `services/spatial_geometry.py` implements geometry,
`services/spatial.py` consumes stored tracking frames, and `schemas/spatial.py`
validates polygon inputs, grids, frame counts, chronology and summaries.
There are no new CV-service endpoints, decoding passes or inference dependencies.

## Coordinates and membership

Persistent coordinates are normalized to [0,1], with a top-left origin. After
clipping a tracked-person box to the image, its foot point is
`x = (x1 + x2) / (2 * width)`, `y = y2 / height`. Empty intersections are skipped.
The foot point approximates where the person stands better than the box center;
it remains an image-space approximation, not physical localization. Existing
Phase 5 box-center trajectories retain their original meaning.

Polygons have 3–50 distinct finite vertices, each coordinate in [0,1], normalized
area greater than 1e-10, and no self-intersection, self-touch or overlapping
adjacent edges. The closing edge is implicit: do not repeat the first vertex.
Names are trimmed, 1–100 characters; descriptions are optional, at most 1000.
Each video allows at most 50 zones to bound synchronous work. Unknown input
fields and null name/polygon/active updates are rejected. Description can be cleared.

Membership uses even/odd ray casting. Points on edges or vertices count inside,
with an absolute 1e-10 floating-point tolerance for the cross product and bounds.
Concave simple polygons work. Zones overlap independently: the same observation
may belong to multiple zones, so zone counts must not be summed into attendance.

## Heatmaps

The default grid is 32 columns by 18 rows, configurable through backend
`HEATMAP_GRID_WIDTH` and `HEATMAP_GRID_HEIGHT`, each bounded to 1–128. Each valid
tracked-person foot point increments one cell: `floor(x * columns)`,
`floor(y * rows)`, capped at the last column/row for coordinates equal to 1.
Rows run top to bottom; columns run left to right. Every processed tracking frame
contributes, including repeated observations of the same anonymous track.

`videos.heatmap_analysis` is nullable JSON containing schema version 1, grid
dimensions, the raw count grid, total valid observations, maximum cell count,
hottest `(column,row)` and its normalized center. Ties use the first cell in
row-major order. Empty grids have zero totals and null hottest-cell values.
Counts remain the source of truth. The UI derives `count / maximum`, or zero
when the maximum is zero. Intensity is relative observation intensity, not a
probability. No smoothing, masks, rendered heatmap files or synthetic observations
are persisted. A video upload calculates the heatmap within the same backend
transaction as detection, tracking and crowd results.

The heatmap means “where anonymous tracked-person observations occurred across
the analyzed video.” It is not unique people per location, physical foot traffic,
people/m², exact dwell time, or a danger/risk map. It weights processed frames,
so comparisons between different FPS/strides/durations need care.

## Zones, API and persistence

Migration **20260916_06**, following **20260915_05**, adds the heatmap column and
`monitoring_zones`. Migrations 01–05 are unchanged. Zones contain UUID, indexed
video UUID, name, description, normalized polygon JSON, active flag, timestamps
and nullable analysis JSON. Ownership is inherited through the parent video.
The foreign key uses `ON DELETE CASCADE`; ORM relationship cleanup is also defined.
Deleting the video removes heatmap and zones/analytics with its existing media cleanup.

Authenticated routes under `/api/v1/videos/{video_id}`:

- `POST /zones`, `GET /zones`
- `GET /zones/{zone_id}`, `PATCH /zones/{zone_id}`, `DELETE /zones/{zone_id}`
- `POST /heatmap`: lightweight backfill/rebuild from stored tracking for earlier videos.

Every endpoint first checks video ownership. Missing and other-user videos both
return 404; absent authentication returns 401; malformed UUIDs/inputs return 422.
Zone UUIDs are scoped to the owned video. Responses exclude internal paths.
Writes lock the owned video row to serialize concurrent zone writes. JSON results
are assigned and committed once per request, never once per frame.

Creation and updates recalculate zone analytics from `video.tracking_analysis`
and dimensions, including zones created after analysis. No call path reaches
YOLO or ByteTrack. Backend tests replace both the CV HTTP call and upload-analysis
entry point with functions that raise if called, then create, edit, rename,
deactivate/reactivate and backfill. Inactive zones have null analytics; reactivation
rebuilds them. Videos without tracking can store zones with null analytics.

Zone frame schema: `frame_index`, `timestamp_seconds`, `active_tracks_in_zone`,
`track_ids_in_zone` (sorted, distinct, anonymous IDs). No boxes are duplicated.
Count means simultaneous active anonymous tracks whose foot points are inside.

Summary schema: `processed_frames`, `frames_with_people`,
`maximum_simultaneous_tracks`, `average_simultaneous_tracks`,
`median_simultaneous_tracks`, `earliest_peak_frame`,
`earliest_peak_timestamp_seconds`, `distinct_anonymous_track_ids`,
`total_track_observations`. Means and medians include empty processed frames.
Empty timelines have null peaks; all-zero nonempty timelines peak at their first
frame. Ties choose the earliest observed frame. Distinct IDs are anonymous tracking
instances, not guaranteed unique people; total observations are not visitors.

Polygon-intersection image occupancy is deferred: a robust union/clipping
implementation is disproportionate here, and bounding-box overlap is not a
substitute. Dwell duration is also deferred rather than bridging unobserved gaps.
If introduced later, `observed_zone_duration_seconds` must derive from timestamps
and explicitly handle misses, exits and re-entry; it must not claim exact dwell time.

## UI and limits

The Video Analysis page has a Spatial Analysis disclosure with textual heatmap
summary, relative-intensity legend, show/hide controls and opacity. SVG layers and
the representative annotated JPEG share the source aspect ratio. Rendering scales
normalized vertices into the SVG viewBox; clicks use the SVG's actual bounds.
Responsive resizing never changes stored geometry. Without a preview, the
source-aspect analysis canvas remains available. Existing track labels are baked
into the representative JPEG; they are not live counts or independently toggleable.

Create a named zone by clicking vertices, then save; undo, clear and cancel are
available. Keyboard users can enter normalized x/y points. Select zones using
buttons, edit name/description or redraw polygon, deactivate/reactivate, or delete.
The server is authoritative for full polygon validation and retains the draft on
rejection. Names/descriptions use React text rendering. Selected-zone metrics,
count timeline and expandable numerical table all use persisted analysis.

Perspective, occlusion, camera movement, imprecise boxes, sampling, tracker
fragmentation and ID switches affect results. There is no calibration, physical
localization, face recognition, embeddings, re-identification, cross-video identity,
demographics, alerts, capacities, risk scores, notifications, live feeds or WebSockets.
Short clips remain the scope: synchronous CPU computation and whole JSON responses
are not intended for unbounded video histories. Runtime is linear in observations
times polygon vertices for each zone; heatmaps use fixed grid memory.

## Verification

Run CV/backend suites, frontend tests/lint/build and Compose config checks as in
[development](development.md). Spatial unit tests live in the backend because it
owns the math. Migration tests use an isolated transactional PostgreSQL schema.

After uploading a real person-containing clip through the browser, run from backend:

```powershell
.venv/Scripts/python.exe scripts/verify_spatial.py VIDEO_UUID ../storage/phase7-verification/spatial-report.json
```

This checks every cell against an independent box-coordinate oracle, total counts,
normalization and deterministic recalculation; compares pedestrian-path versus
quiet-region zones and benchmarks heatmap plus two zones over 30 runs. Use ignored
local verification media only. The browser gate must also cover two zones, polygon
edit, rename, refresh, deactivate/reactivate, deletion and database/media cascade
cleanup before declaring Phase 7 complete.
