from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "crowd-monitoring-backend"
    environment: str = "development"
    database_url: str = "postgresql+psycopg://crowd:crowd@localhost:5432/crowd_monitoring"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    secret_key: str = "development-only-change-me"
    jwt_secret_key: str = "development-only-replace-before-deployment"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    @property
    def cors_origin_list(self) -> list[str]: return [item.strip() for item in self.cors_origins.split(",") if item.strip()]
@lru_cache
def get_settings() -> Settings: return Settings()
