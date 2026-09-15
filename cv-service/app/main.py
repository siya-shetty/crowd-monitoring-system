from fastapi import FastAPI
app = FastAPI(title="Crowd Monitoring CV Service", version="0.1.0")
@app.get("/health", tags=["system"])
def health() -> dict[str, str]: return {"status":"ok", "service":"crowd-monitoring-cv-service", "mode":"foundation-only"}
