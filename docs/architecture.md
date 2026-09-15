# Architecture

Phase 1 establishes independent deployment boundaries without implementing computer vision or real-time processing.

```mermaid
flowchart LR
  F[React + TypeScript frontend] -->|HTTP /api/v1| B[FastAPI backend]
  B -->|SQLAlchemy 2.x| P[(PostgreSQL)]
```

The planned future flow is intentionally not implemented:

```mermaid
flowchart LR
  C[Camera or uploaded video] --> CV[CV service]
  CV --> B[FastAPI]
  B -. future WebSocket .-> F[Frontend]
```

The frontend owns presentation, navigation, client state, and the typed API boundary. FastAPI owns validation, orchestration, domain services, and persistence. The CV service is a separate future compute boundary. Aggregate monitoring is the project goal: facial recognition and biometric identification are out of scope.
