"""Configuration management for Community Service Desk."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_prefix="CSD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = False

    secret_key: str = "dev-insecure-secret-key-change-in-production-32charsmin!"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480

    database_url: str = "postgresql+psycopg://csd_user:csd_password@localhost:5433/csd_db"

    storage_backend: str = "local"
    storage_local_dir: str = "./uploads"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB

    host: str = "127.0.0.1"
    port: int = 8000

    cookie_name: str = "csd_session"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def uploads_path(self) -> Path:
        p = Path(self.storage_local_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
