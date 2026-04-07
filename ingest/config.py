from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ingest_api_token: str
    application_id: str
    device_profile_id: str = ""
    lw010_profile_id: str = ""
    chirpstack_api_url: str
    chirpstack_api_token: str
    ingest_data_dir: str = "/opt/chirpstack-ingest"
    upload_dir: str = ""
    db_path: str = ""
    max_upload_bytes: int = 10 * 1024 * 1024

    @property
    def resolved_device_profile_id(self) -> str:
        return self.device_profile_id or self.lw010_profile_id

    @property
    def resolved_upload_dir(self) -> Path:
        if self.upload_dir:
            return Path(self.upload_dir)
        return Path(self.ingest_data_dir) / "uploads"

    @property
    def resolved_db_path(self) -> Path:
        if self.db_path:
            return Path(self.db_path)
        return Path(self.ingest_data_dir) / "data" / "jobs.db"


def load_settings() -> Settings:
    return Settings()
