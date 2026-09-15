# Development

Copy `.env.example` to `.env`; do not commit it. Python 3.12+ is required (the verified host uses `py -3.13`).

Install and run locally:

```powershell
cd frontend; npm install; npm run dev
cd backend; py -3.13 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn app.main:app --reload
cd cv-service; py -3.13 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn app.main:app --reload --port 8001
```

Start PostgreSQL and all services with `docker compose up --build` when Docker Desktop is available. Use `npm test`, `npm run build`, `py -3.13 -m pytest`, and `git diff --check` before submitting changes.

## Authentication database setup

After PostgreSQL is running, apply the versioned schema with `cd backend; .\.venv\Scripts\alembic.exe upgrade head`. Registration creates a default `viewer` account and redirects to the login screen; it does not automatically create a browser session.

## Phase 3 video inspection

Set `VIDEO_STORAGE_PATH`, `MAX_UPLOAD_SIZE_BYTES`, and `CV_SERVICE_URL` in `.env` (the example defaults to local development values). The backend generates a storage key and writes the upload outside source-controlled directories, records its metadata in PostgreSQL, and posts the stored bytes to `cv-service`'s `/inspect` endpoint. OpenCV verifies the file and returns duration, dimensions, FPS, and frame count; the database status changes from `uploaded` through `processing` to `completed` or `failed`.

Docker Compose mounts the named `video-storage` volume at `/data/videos` in the backend and resolves the CV service as `http://cv-service:8001`. The CV service uses `opencv-python-headless`; use local filesystem storage only for development. An object-storage adapter and queued jobs should replace synchronous inspection before a multi-instance deployment. YOLO, detection, tracking, and crowd analytics are intentionally not part of Phase 3.

## Phase 4 person detection

The CV service lazily loads Ultralytics' official pretrained `yolo11n.pt` model once per process. Each `YOLO_FRAME_STRIDE`-th frame is decoded and inferred on; lower strides improve temporal coverage but increase CPU time, while higher strides are faster and can miss short-lived people. Only COCO's `person` class is serialized. The backend validates the CV JSON response before persisting the summary and sampled-frame results as JSON columns on `videos`; no filesystem path is returned. Synchronous inference is for development only. Confidence is a model score, not a measured accuracy percentage. Person detections are not unique people: Phase 4 intentionally has no tracking or identity features.
