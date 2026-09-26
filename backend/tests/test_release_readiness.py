import io
from uuid import uuid4

import jwt
import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.services.auth import decode_access_token
from app.services.video_storage import VideoStorage


def production(**overrides):
    return Settings(_env_file=None, **(dict(environment='production',
        jwt_secret_key='a9f7c2b4e8d631005abcdef987654321ab',
        database_url='postgresql+psycopg://user:password@db/app',
        cv_service_url='http://cv-service:8001', cors_origins='https://app.example.com') | overrides))


def test_production_valid_configuration():
    assert production().cors_origin_list == ['https://app.example.com']


def test_configuration_errors_do_not_display_secrets():
    secret = 'private-test-value-never-display-in-errors'
    with pytest.raises(ValidationError) as error:
        production(jwt_secret_key=secret, cors_origins='*')
    assert secret not in str(error.value)


@pytest.mark.parametrize('values', [
    {'jwt_secret_key': 'short'},
    {'jwt_secret_key': 'development-only-replace-with-a-long-random-secret'},
    {'cors_origins': '*'}, {'cors_origins': 'http://app.example.com'},
    {'cors_origins': 'https://app.example.com/'}, {'cors_origins': ''},
    {'database_url': ''}, {'cv_service_url': ''}, {'jwt_algorithm': 'none'},
    {'max_upload_size_bytes': 0}, {'access_token_expire_minutes': 0},
    {'environment': 'prodution'},
])
def test_unsafe_configuration_rejected(values):
    with pytest.raises(ValidationError):
        production(**values)


def test_production_missing_configuration_rejected(monkeypatch):
    for key in ('DATABASE_URL', 'JWT_SECRET_KEY', 'CORS_ORIGINS', 'CV_SERVICE_URL'):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment='production')


def test_token_requires_expiration():
    token = jwt.encode({'sub': str(uuid4())}, get_settings().jwt_secret_key, algorithm='HS256')
    assert decode_access_token(token) is None


def test_upload_limit_and_read_failure_cleanup(tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), 'video_storage_path', str(tmp_path))
    monkeypatch.setattr(get_settings(), 'max_upload_size_bytes', 4)
    storage = VideoStorage()
    headers = Headers({'content-type': 'video/mp4'})
    with pytest.raises(ValueError, match='limit'):
        storage.save(UploadFile(io.BytesIO(b'12345'), filename='clip.mp4', headers=headers))
    class BrokenStream(io.BytesIO):
        def read(self, size=-1):
            raise OSError('read interrupted')
    with pytest.raises(OSError):
        storage.save(UploadFile(BrokenStream(), filename='clip.mp4', headers=headers))
    assert not list(tmp_path.iterdir())
    for key in ('../outside.jpg', '..', '/outside.jpg', 'sub\\outside.jpg'):
        with pytest.raises(ValueError):
            storage.path_for(key)
