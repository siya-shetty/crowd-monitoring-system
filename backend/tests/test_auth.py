import uuid
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User

client = TestClient(app)
def credentials() -> dict[str, str]:
    suffix = uuid.uuid4().hex
    return {"full_name":"Phase Two Test", "email":f"phase2-test-{suffix}@example.com", "password":"SecurePass123"}
def test_registration_creates_hashed_viewer_user() -> None:
    payload = credentials(); response = client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201; assert "hashed_password" not in response.json(); assert response.json()["role"] == "viewer"
    with SessionLocal() as database:
        user = database.scalar(select(User).where(User.email == payload["email"]))
        assert user is not None and user.hashed_password != payload["password"]
def test_duplicate_registration_is_rejected() -> None:
    payload = credentials(); assert client.post("/api/v1/auth/register", json=payload).status_code == 201
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409
def test_login_and_current_user() -> None:
    payload = credentials(); client.post("/api/v1/auth/register", json=payload)
    login = client.post("/api/v1/auth/login", json={"email":payload["email"], "password":payload["password"]})
    assert login.status_code == 200 and login.json()["token_type"] == "bearer"
    me = client.get("/api/v1/auth/me", headers={"Authorization":f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200 and me.json()["email"] == payload["email"]
def test_incorrect_password_and_invalid_tokens_are_rejected() -> None:
    payload = credentials(); client.post("/api/v1/auth/register", json=payload)
    assert client.post("/api/v1/auth/login", json={"email":payload["email"], "password":"WrongPassword123"}).status_code == 401
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization":"Bearer invalid-token"}).status_code == 401
