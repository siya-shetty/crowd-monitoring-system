# Development

## Local setup

Copy `.env.example` to `.env`; never commit it. Start PostgreSQL with `docker compose up -d postgres`. From each service directory create its own Python environment and install requirements. The verified host uses Python 3.13.

```powershell
# backend
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/alembic.exe upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
```

```powershell
# cv-service: install CPU wheels first
py -3.13 -m venv .venv
.venv/Scripts/python.exe -m pip install --index-url https://download.pytorch.org/whl/cpu torch==2.14.0 torchvision==0.29.0
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m uvicorn app.main:app --env-file ../.env --port 8001
```

Backend settings load a `.env` in its working directory; use shell environment variables or `--env-file ../.env` for the server when using the root file. Alembic also needs DATABASE_URL in its environment if it differs from the local default. CV settings read process environment; root `.env` is not automatically loaded without `--env-file`. Restart services after configuration changes. Model weights download on first use and stay outside version control.

```powershell
# frontend
npm install
npm run dev
```

Use [frontend](http://localhost:5173), [backend health](http://localhost:8000/health), and [CV health](http://localhost:8001/health). Health does not eagerly load model weights.

## Checks

```powershell
# Run from each respective directory
.venv/Scripts/python.exe -m pytest tests -q
npm test
npm run lint
npm run build
# Repository root
docker compose config --quiet
git diff --check
git status --untracked-files=all
```

Backend tests require local PostgreSQL at Alembic head `20260916_06` and create disposable test users. CV unit tests use deterministic fake tracker results; they do not load YOLO. Backend migration coverage uses transaction-local temporary tables or an isolated transactional schema and never downgrades the real database.

## Real tracking gate

Download the public [OpenCV vtest.avi sample](https://github.com/opencv/opencv/blob/master/samples/data/vtest.avi) to ignored storage, or supply your own appropriately authorized person-containing clip. From `cv-service`:

```powershell
.venv/Scripts/python.exe scripts/verify_tracking.py ../storage/phase5-verification/source.avi ../storage/phase5-verification
```

This generates a 40-consecutive-frame MP4, performs real CPU YOLO/ByteTrack twice, checks ID continuity and moving trajectories, tests interleaved real tracker instances, and saves an ignored numerical report. It requires actual people; fabricated movement of a still image is not used as tracking evidence.

Then use the browser to sign in, upload the MP4, inspect detection/tracking metrics, preview labels and selected trajectories, refresh, and delete. Verify the database record and stored upload/preview disappear. Do not commit verification media or credentials.

## Configuration and trade-offs

See [README](../README.md) for defaults and [architecture](architecture.md) for contracts. Detection reporting stride and tracking stride are independent; inference is shared on their union. Detection confidence remains a reporting filter. ByteTrack uses retained person detections at its low threshold, initializes at its high threshold, and never receives other COCO classes.

Every-frame tracking is the default for continuity. Increasing tracking stride reduces work only on frames not otherwise needed for detection reporting, weakens association, and changes the real-time interval represented by the lost-track buffer. Skipped source frames are not tracked. All timestamps refer to the original source index / FPS, not elapsed processing time.

## Docker

The CV Dockerfile installs CPU-only PyTorch/Torchvision wheels before requirements, plus OpenCV runtime libraries. No NVIDIA container runtime or CUDA device is required. `lap` is installed explicitly, avoiding dependency installation during a request. Ultralytics is pinned because the adapter depends on its tested tracker extension point. Review and rerun both real and mocked gates before upgrading it.

Compose forwards YOLO/tracker and crowd count threshold configuration. Model weights are downloaded at runtime rather than copied from the host build context. Source media and previews live in the backend's named storage volume until deletion. Compose is a development foundation; configure authentication secrets and production storage/security separately.

## Privacy and quality

Anonymous labels only describe continuity inside one analyzed video. `distinct_track_ids != guaranteed unique real-world people`. Occlusions, crowded scenes, misses, ID switches, fragmentation, exits/re-entry, camera motion and frame sampling cause errors. Confidence is a detector score, not measured tracking accuracy. Normalized center trajectories are not calibrated distances or speeds. No identity, face, demographic, re-identification, or later-phase alerting features are present.

## Phase 6 verification

See [crowd analysis](crowd-analysis.md#verification) for deterministic tests, the real CPU crowd gate, and the required browser workflow. Start or restart both services after deploying Phase 6; the backend requires the new crowd response contract.

## Phase 7 verification

Spatial math tests run in the backend suite; the CV wire contract is unchanged.
Restart the backend after migrating; no new inference dependencies are required.
Use the Spatial Analysis disclosure in `/videos`. Existing videos with tracking
can use “Generate heatmap from stored tracking”; zones can be created after upload.
See [spatial verification](spatial-analysis.md#verification) for the independent
real-data oracle, CPU benchmark and complete browser gate.

For backend tests in Docker, mount the repository read-only and run from its
backend directory: the existing contract-mirror tests also read CV source files,
which are intentionally absent from the standalone backend production image.
