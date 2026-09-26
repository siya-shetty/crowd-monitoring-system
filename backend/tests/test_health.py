from fastapi.testclient import TestClient
from app.main import app
def test_health_endpoint_returns_service_identity() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "crowd-monitoring-backend"

def test_health_reports_database_failure(monkeypatch):
    monkeypatch.setattr('app.services.health.database_is_available', lambda: False)
    response = TestClient(app).get('/health')
    assert response.status_code == 503
    assert response.json()['status'] == 'unavailable'
