from fastapi.testclient import TestClient
from app.main import app
def test_health_endpoint_returns_service_identity() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "crowd-monitoring-backend"
