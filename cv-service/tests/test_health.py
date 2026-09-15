from fastapi.testclient import TestClient
from app.main import app
def test_cv_health_endpoint() -> None:
    assert TestClient(app).get("/health").json()["mode"] == "person-detection"
