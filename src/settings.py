from datetime import date
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DATAGUARD_", env_file=PROJECT_ROOT / "environment" / "back-end.env", extra="ignore"
    )

    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_rows: int = Field(default=50_000, gt=0)
    max_columns: int = Field(default=1000, gt=0)
    max_cells: int = Field(default=2_000_000, gt=0)
    max_decoded_bytes: int = Field(default=50 * 1024 * 1024, gt=0)
    statistical_min_samples: int = Field(default=20, ge=1)
    iqr_multiplier: float = Field(default=1.5, ge=0, allow_inf_nan=False)
    missingness_increase_percentage_points: float = Field(default=5, ge=0, le=100)
    row_count_change_percentage: float = Field(default=20, ge=0, allow_inf_nan=False)
    category_share_change_percentage_points: float = Field(default=10, ge=0, le=100)
    finding_sample_size: int = Field(default=20, ge=1, le=1000)
    top_category_count: int = Field(default=5, ge=1, le=100)
    actor: str = Field(default="local_operator", min_length=1)
    reference_date: date | None = None
    rules_path: Path = PROJECT_ROOT / "config" / "facilities.yaml"
    storage_dir: Path = PROJECT_ROOT / "storage"

