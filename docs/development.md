# Development

Copy `.env.example` to `.env`; do not commit it. Python 3.12+ is required (the verified host uses `py -3.13`).

Install and run locally:

```powershell
cd frontend; npm install; npm run dev
cd backend; py -3.13 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn app.main:app --reload
cd cv-service; py -3.13 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; uvicorn app.main:app --reload --port 8001
```

Start PostgreSQL and all services with `docker compose up --build` when Docker Desktop is available. Use `npm test`, `npm run build`, `py -3.13 -m pytest`, and `git diff --check` before submitting changes.
