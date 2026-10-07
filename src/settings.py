from datetime import date
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATAGUARD_", env_file=".env", extra="ignore"
    )

    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_rows: int = Field(default=50_000, gt=0)
    finding_sample_size: int = Field(default=20, ge=1, le=1000)
    top_category_count: int = Field(default=5, ge=1, le=100)
    actor: str = Field(default="local_operator", min_length=1)
    reference_date: date | None = None
    rules_path: Path = PROJECT_ROOT / "config" / "facilities.yaml"

