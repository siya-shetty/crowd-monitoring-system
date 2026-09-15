# Phase 6: crowd counting and image-space analysis

## Definitions and mathematics

**Observed crowd count** is the number of simultaneous active anonymous person
tracks in a processed tracking frame. ByteTrack lost predictions are excluded.
This is not attendance, unique visitors, or population outside the camera view.
Never sum counts into a unique-person estimate. **Distinct track IDs** describe
anonymous tracking instances over time and are not guaranteed unique people.

**Image occupancy** = area of the union of active tracked-person rectangles /
(image width × image height), in [0, 1]. The frontend multiplies by 100 for percent.
Rectangles are clipped to image boundaries. Reversed, degenerate, and fully
outside rectangles cover zero area; non-finite coordinates are rejected. The
tracking contract rejects invalid observations before this stage.

The union algorithm partitions x coordinates into slabs and merges overlapping
y intervals within each slab. It integrates continuous box area exactly without
double-counting overlaps. Runtime is O(n² log n) in active rectangles with O(n)
temporary memory, independent of image resolution. It allocates no image masks.
This is suitable for the current short-clip scope; extremely large active counts
may warrant a segment-tree sweep in a later performance change.

**Crowd concentration** = `1 - sqrt(2 * (Var(x) + Var(y)))`, using population
variances of normalized box-center coordinates. For coordinates in [0, 1], each
variance is at most 1/4, bounding the score to [0, 1]. Tighter clusters have higher
scores; maximally separated opposite corners approach zero. Fewer than two
valid boxes return zero. Final floating-point output is clamped to [0, 1].
This measures center spread, not interpersonal distance or headcount. A tightly
clustered pair can score highly. No weighted combined density score is introduced.

**Crowd level** uses only observed count. Inclusive lower boundaries are:

| Environment variable | Default | Category |
| --- | --- | --- |
| CROWD_MODERATE_COUNT | 5 | MODERATE |
| CROWD_HIGH_COUNT | 10 | HIGH |
| CROWD_VERY_HIGH_COUNT | 20 | VERY_HIGH |

Counts below the first boundary are LOW, including zero. Values must be positive
integers with moderate < high < very high. These are configurable operational
indicators, dependent on camera and context, not validated universal safety
standards. HIGH does not automatically mean unsafe. Configuration is stored with
each analysis; changes apply to new analyses only. Compose forwards these values.

**Count delta** is current minus previous processed-frame count. The first delta
is zero. It is not time-normalized and is not a flow rate.

**Trend** fits an ordinary least-squares line over the last ten processed tracking
observations. Multiply its slope (counts per observation) by nine to obtain fitted
change across the window. Change ≥ 1 means increasing, ≤ -1 decreasing, otherwise
stable. Fewer than ten observations are stable. This smooths individual changes,
is descriptive rather than predictive, and does not implement alerts. The fixed
window and change boundary are versioned in stored configuration. Actual window
duration depends on FPS and tracking stride; it is not a fixed-second window.

## Contract and persistence

`cv-service/app/crowd/analysis.py` owns image geometry; `aggregation.py` consumes
existing TrackingFrame results. `config.py` reads the three environment settings;
`schemas.py` defines the versioned contract, deterministic trend and summary
consistency checks. No additional inference or video decoding is performed.
The backend mirrors the deployment-independent contract and validates the full
CV response before saving results. A mirror test prevents silent schema drift.

Migration **20260915_05**, after 04, adds nullable `videos.crowd_analysis` JSON.
Versions 01–04 are unchanged. Existing rows remain readable with crowd analysis
unavailable. New CV responses must contain crowd data; deployment requires
updating both services. An incompatible or malformed response fails safely.

Stored document: `{schema_version: 1, config, frames, summary}`. Each frame stores:

- frame_index, timestamp_seconds
- observed_crowd_count, image_occupancy_ratio, crowd_concentration
- crowd_level, crowd_count_delta, crowd_trend

No boxes, images, masks, or identifiers are duplicated in this document. Summary:

- processed_crowd_frames, frames_with_observed_people
- minimum/maximum/average/median_observed_crowd_count
- peak_crowd_frame, peak_crowd_timestamp_seconds
- average_image_occupancy, maximum_image_occupancy
- peak_occupancy_frame, peak_occupancy_timestamp_seconds
- average_crowd_concentration, maximum_crowd_concentration
- level_distribution (all four levels, frame counts and percentages)
- final_crowd_trend

Statistics weight processed frames equally. No observed count is interpolated
into skipped source frames. Level distribution reports frames rather than exact
time spent at each level. Tied peaks use the earliest frame. An empty frame list
has zero statistics and null peaks; a nonempty all-zero sequence peaks at its
first observation. Concentration averages include the documented zero values.

Validation rejects extra fields, NaN/Infinity, invalid ranges, negative/fractional
counts, inconsistent chronology, levels, deltas and trends. It recomputes all
summary statistics and distribution entries, including earliest peaks. The full
backend contract checks crowd frame count/index/timestamp/count against tracking.
The backend does not rerun image geometry. Results are committed atomically;
failures roll back analysis and remove any newly written preview.

## UI

The owner-protected Video Analysis page displays peak/average observed crowd,
earliest peak time, mean/max image occupancy, mean concentration, final trend,
a count timeline with level tooltips, an image occupancy percent timeline, and
frame distribution across levels. An expandable table exposes every observation,
delta, and trend. Earlier analyses and failures have explicit status text.
The existing authenticated Track-ID JPEG, detections, tracking and trajectories
remain available. No additional preview rendering is needed for this phase.

## Limits and privacy

Image occupancy is **not physical venue occupancy**. These image-space measures
are **not people/m²**, physical area density, calibrated distance, or risk scores.
Camera angle/perspective, occlusion, box-size variation, tracker fragmentation,
camera movement and sampling all affect results. No camera calibration exists.
Counts are observations subject to detector/tracker error, not ground truth.

No faces, embeddings, demographics, biometrics, re-identification or cross-video
identity are introduced. Media and previews remain local sensitive artifacts,
retained until owner deletion. No alerts, heatmaps, zones, capacities, live-camera
feeds, WebSockets, reports or later-phase features are added. Synchronous
processing and per-video JSON remain suited to short development clips.

## Verification

Run all CV/backend/frontend suites and frontend lint/build as documented in
[development](development.md). Migrate the local database to head before tests.
Migration tests use a transaction-local temporary table and never downgrade the
real videos table. Geometry tests use synthetic rectangles and a separate pixel
cell oracle for random integer boxes, without YOLO.

From `cv-service`, reuse a local authorized real pedestrian clip:

```powershell
.venv/Scripts/python.exe scripts/verify_crowd.py ../storage/phase5-verification/pedestrians.mp4 ../storage/phase6-verification
```

This runs real OpenCV → CPU YOLO11 → ByteTrack → crowd analytics, independently
checks a populated frame's union by two-axis cell partitioning, reports real
overlap evidence, and times 30 deterministic crowd aggregations. Output contains
the full wire response and numerical report under ignored storage; never commit
the clip, weights, previews or generated analysis. The benchmark includes crowd
contract validation and excludes decoding/inference; the pipeline comparison is
a measured reference ratio rather than a controlled inference-only benchmark.

Complete the real browser gate: login → videos → upload clip → completed results
and preview → inspect charts/distribution/trend → refresh → confirm persistence
→ delete disposable test upload → verify database row, media and preview cleanup.
Numerical results and final gate outcomes are recorded in the Phase 6 review report.
