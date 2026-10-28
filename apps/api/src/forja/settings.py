from __future__ import annotations

from functools import cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORJA_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    database_url: str = ""  # default: SQLite inside data_dir
    max_upload_mb: int = 500
    preview_timeout_s: float = 15.0
    preview_limit: int = 500
    duckdb_memory_limit: str = "2GB"
    duckdb_threads: int = 4
    cache_max_gb: float = 2.0
    auto_migrate: bool = True
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    export_workers: int = 2

    @property
    def db_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{(self.data_dir / 'forja.db').resolve().as_posix()}"


@cache
def get_settings() -> Settings:
    s = Settings()
    s.data_dir = s.data_dir.resolve()
    s.data_dir.mkdir(parents=True, exist_ok=True)
    return s
