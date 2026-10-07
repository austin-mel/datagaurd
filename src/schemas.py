from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from src.rules import RuleSet


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(ApiModel):
    status: str = Field(default="ok", examples=["ok"])


class ErrorDetail(ApiModel):
    code: str
    message: str
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ErrorResponse(ApiModel):
    error: ErrorDetail


class DatasetMetadata(ApiModel):
    original_filename: str = Field(examples=["facilities_clean.csv"])
    content_sha256: str
    size_bytes: int
    encoding: str = "utf-8"
    row_count: int
    column_count: int
    headers: list[str]
    record_number_base: int = 1


class UploadResponse(ApiModel):
    metadata: DatasetMetadata
    persisted: bool = False


class CategoryCount(ApiModel):
    value: str
    count: int


class ColumnProfile(ApiModel):
    column: str
    observed_types: list[Literal["integer", "number", "date", "text"]]
    missing_count: int
    nonmissing_count: int
    distinct_count: int
    numeric_count: int
    numeric_min: float | None
    numeric_max: float | None
    top_categories: list[CategoryCount]


class DatasetProfile(ApiModel):
    row_count: int
    column_count: int
    columns: list[ColumnProfile]


class ProfileResponse(ApiModel):
    metadata: DatasetMetadata
    profile: DatasetProfile


class RecordSample(ApiModel):
    record_number: int
    value: str


class Finding(ApiModel):
    rule_id: str
    column: str | None
    category: Literal["validation"] = "validation"
    severity: Literal["error", "warning"]
    explanation: str
    observed_result: dict[str, JsonValue]
    threshold: dict[str, JsonValue]
    affected_count: int
    record_samples: list[RecordSample]
    affected_record_numbers: list[int]


class RuleResult(ApiModel):
    rule_id: str
    column: str | None
    status: Literal["passed", "failed", "skipped"]
    evaluated_count: int
    skipped_count: int
    reason: str | None = None


class CheckResponse(ProfileResponse):
    processing_status: Literal["completed"] = "completed"
    validation_status: Literal["passed", "failed"]
    findings: list[Finding]
    rule_results: list[RuleResult]
    reference_date: date
    checked_at: datetime
    actor: str
    implementation_version: str
    configuration: RuleSet
    configuration_sha256: str
    settings_snapshot: dict[str, JsonValue]
    baseline_id: str | None = None



