from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")
    database_url: str = "postgresql+psycopg://iwardrobe:local-development@127.0.0.1:5433/iwardrobe"
    redis_url: str = "redis://127.0.0.1:6380/0"
    data_dir: Path = ROOT / ".local" / "data"
    cookie_secure: bool = False
    allowed_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    session_hours: int = 24
    max_upload_bytes: int = 20 * 1024 * 1024
    model_cache_dir: Path = ROOT / ".local" / "models"
    cutout_threads: int = 2


@lru_cache
def settings() -> Settings:
    return Settings()
