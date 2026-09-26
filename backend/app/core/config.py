from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator
from typing import Literal
from urllib.parse import urlsplit

class Settings(BaseSettings):
    app_name: str = "crowd-monitoring-backend"
    environment: Literal['development', 'test', 'production'] = "development"
    database_url: str = "postgresql+psycopg://crowd:crowd@localhost:5432/crowd_monitoring"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    secret_key: str = "development-only-change-me"
    jwt_secret_key: str = "development-only-replace-before-deployment"
    jwt_algorithm: Literal['HS256'] = "HS256"
    access_token_expire_minutes: int = Field(default=60, gt=0)
    video_storage_path: str = "storage/videos"
    max_upload_size_bytes: int = Field(default=104857600, gt=0)
    cv_service_url: str = "http://localhost:8001"
    cv_analysis_timeout_seconds: float = Field(default=600, gt=0, le=3600)
    heatmap_grid_width: int = Field(default=32, ge=1, le=128)
    heatmap_grid_height: int = Field(default=18, ge=1, le=128)
    live_ws_subscriber_cap: int = Field(default=4, ge=1, le=16)
    live_target_fps: float = Field(default=3, gt=0, le=10)
    live_max_frame_bytes: int = Field(default=524288, ge=1024, le=2097152)
    live_recent_observations: int = Field(default=300, ge=10, le=1000)
    live_session_stale_seconds: float = Field(default=10, ge=2, le=60)
    live_max_sessions: int = Field(default=8, ge=1, le=32)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)
    @model_validator(mode='after')
    def production_configuration(self):
        if self.environment == 'production':
            secret = self.jwt_secret_key.strip()
            if len(secret) < 32 or any(word in secret.lower() for word in ('development', 'replace', 'change-me')):
                raise ValueError('Production requires a random JWT_SECRET_KEY of at least 32 characters')
            if 'database_url' not in self.model_fields_set or not self.database_url.startswith('postgresql'):
                raise ValueError('Production requires an explicit PostgreSQL DATABASE_URL')
            if 'cv_service_url' not in self.model_fields_set or not self.cv_service_url.startswith(('http://', 'https://')):
                raise ValueError('Production requires an explicit CV_SERVICE_URL')
            if 'cors_origins' not in self.model_fields_set or not self.cors_origin_list:
                raise ValueError('Production requires explicit CORS_ORIGINS')
            for origin in self.cors_origin_list:
                url = urlsplit(origin)
                if url.scheme != 'https' or not url.hostname or '*' in origin or url.username or url.password or url.path or url.query or url.fragment:
                    raise ValueError('Production CORS_ORIGINS must contain exact HTTPS origins without paths')
        return self
    @property
    def cors_origin_list(self) -> list[str]: return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
@lru_cache
def get_settings() -> Settings: return Settings()
