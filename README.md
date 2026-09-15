# Crowd Monitoring and Crowd Safety System

Phase 1 foundation for a privacy-conscious, aggregate crowd-monitoring CSE project. It provides a React command-center shell, a FastAPI health API, PostgreSQL/Alembic infrastructure, and an independently runnable CV-service foundation.

## Stack

React, TypeScript, Vite, Tailwind CSS, React Router, TanStack Query, Framer Motion, Recharts, Lucide; FastAPI, SQLAlchemy 2.x, Pydantic settings, Alembic, PostgreSQL; Docker Compose.

## Quick start

Prerequisites: Node 22+, Python 3.12+, and Docker Desktop for containerized PostgreSQL.

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Or start services independently (install dependencies first):

```powershell
cd frontend; npm install; npm run dev
cd backend; py -3.13 -m pip install -r requirements.txt; py -3.13 -m uvicorn app.main:app --reload
cd cv-service; py -3.13 -m pip install -r requirements.txt; py -3.13 -m uvicorn app.main:app --reload --port 8001
```

Frontend: `http://localhost:5173`; backend health: `http://localhost:8000/health`; CV health: `http://localhost:8001/health`.

## Testing

```powershell
cd frontend; npm test; npm run build
cd backend; py -3.13 -m pytest
cd cv-service; py -3.13 -m pytest
```

## Authentication setup

Apply PostgreSQL migrations before using registration or login:

```powershell
cd backend
.\.venv\Scripts\alembic.exe upgrade head
```

Registration assigns the `viewer` role and redirects the user to login. The frontend stores the access token in browser local storage for this local-development phase; see Current limitations for the security trade-off.

## Current limitations

Dashboard values remain explicitly **DEMO DATA**. Phase 2 adds JWT authentication, but it stores the access token in browser `localStorage` for local development. This is practical for the current single-page architecture but is more exposed to XSS than HttpOnly cookies; production deployment should replace this storage adapter with secure cookie-based sessions. There is no camera connection, upload, video processing, YOLO, tracking, heatmap, risk calculation, WebSocket pipeline, alert engine, or analytics implementation. The system will handle aggregate crowd information only; biometric identification is not planned.

## Future phases

Phase 2 will add secure authentication and the first domain workflows. Subsequent phases can add camera/video integrations, CV processing, live updates, alerts, and historical analytics through the extension boundaries created here. See [architecture](docs/architecture.md) and [development](docs/development.md).
