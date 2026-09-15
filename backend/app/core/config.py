from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    app_name: str = "crowd-monitoring-backend"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://crowd:crowd@localhost:5432/crowd_monitoring"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    secret_key: str = "development-only-change-me"
    jwt_secret_key: str = "development-only-replace-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    video_storage_path: str = "storage/videos"
    max_upload_size_bytes: int = 104857600
    cv_service_url: str = "http://localhost:8001"
    cv_analysis_timeout_seconds: float = Field(default=600, gt=0, le=3600)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def cors_origin_list(self) -> list[str]: return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
@lru_cache
def get_settings() -> Settings: return Settings()
