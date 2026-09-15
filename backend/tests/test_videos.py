import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.v1 import videos as videos_api
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.main import app
from app.models.video import Video, VideoStatus


client = TestClient(app)


def register_and_login() -> dict[str, str]:
    email = f"phase3-video-{uuid.uuid4().hex}@example.com"
    password = "SecurePass123"
    response = client.post(
        "/api/v1/auth/register",
        json={"full_name": "Video Test User", "email": email, "password": password},
    )
    assert response.status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def complete_inspection(database, video: Video) -> Video:
    """Keep API tests independent of a running CV HTTP service."""
    video.status = VideoStatus.COMPLETED
    video.width, video.height, video.fps = 32, 24, 10.0
    video.frame_count, video.duration_seconds = 5, 0.5
    database.commit()
    database.refresh(video)
    return video


def test_video_upload_access_control_and_cleanup(monkeypatch) -> None:
    monkeypatch.setattr(videos_api, "analyze_video", complete_inspection)
    owner = register_and_login()
    other = register_and_login()

    assert client.post("/api/v1/videos", files={"file": ("a.mp4", b"video", "video/mp4")}).status_code == 401
    assert client.post("/api/v1/videos", headers=owner, files={"file": ("notes.txt", b"video", "text/plain")}).status_code == 400
    assert client.post("/api/v1/videos", headers=owner, files={"file": ("empty.mp4", b"", "video/mp4")}).status_code == 400
    monkeypatch.setattr(get_settings(), "max_upload_size_bytes", 4)
    assert client.post("/api/v1/videos", headers=owner, files={"file": ("large.mp4", b"12345", "video/mp4")}).status_code == 400
    monkeypatch.setattr(get_settings(), "max_upload_size_bytes", 100 * 1024 * 1024)

    upload = client.post(
        "/api/v1/videos",
        headers=owner,
        files={"file": ("../../untrusted-name.mp4", b"safe test bytes", "video/mp4")},
    )
    assert upload.status_code == 201
    payload = upload.json()
    assert payload["original_filename"] == "untrusted-name.mp4"
    assert payload["status"] == "completed"

    with SessionLocal() as database:
        video = database.scalar(select(Video).where(Video.id == payload["id"]))
        assert video is not None
        assert video.storage_key != payload["original_filename"]
        assert "/" not in video.storage_key and "\\" not in video.storage_key

    assert [item["id"] for item in client.get("/api/v1/videos", headers=owner).json()] == [payload["id"]]
    assert client.get(f"/api/v1/videos/{payload['id']}", headers=owner).status_code == 200
    assert client.get(f"/api/v1/videos/{payload['id']}", headers=other).status_code == 404
    assert client.delete(f"/api/v1/videos/{payload['id']}", headers=other).status_code == 404
    assert client.get(f"/api/v1/videos/{uuid.uuid4()}", headers=owner).status_code == 404
    assert client.delete(f"/api/v1/videos/{payload['id']}", headers=owner).status_code == 204
    assert client.get("/api/v1/videos", headers=owner).json() == []
