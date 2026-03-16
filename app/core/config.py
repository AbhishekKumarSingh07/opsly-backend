from __future__ import annotations

from functools import lru_cache
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Opsly"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production-use-a-long-random-string"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "postgresql://opsly_user:opsly_pass@localhost:5432/opsly_db"
    REDIS_URL: str = "redis://localhost:6379/0"

    # S3-compatible storage (AWS S3 in prod, MinIO for local dev)
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_S3_BUCKET: str = "opsly-uploads"
    AWS_REGION: str = "us-east-1"
    # Set this to the MinIO URL for local dev; leave blank/unset for real AWS
    S3_ENDPOINT_URL: str = "http://localhost:9000"

    # Office location for attendance geofence
    OFFICE_GPS_LAT: float = 28.6139
    OFFICE_GPS_LNG: float = 77.2090
    GEOFENCE_RADIUS_METERS: float = 100.0

    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Set to True only in production (HTTPS). Keep False for local HTTP dev.
    COOKIE_SECURE: bool = False

    model_config = ConfigDict(env_file=".env", case_sensitive=True)


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()


settings = get_settings()
