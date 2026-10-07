from datetime import date, datetime
from typing import Generic, Literal, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

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


class Metric(ApiModel):
    status: Literal["available", "not_available"] = "not_available"
    numerator: int | None = None
    denominator: int | None = None
    percentage: float | None = None
    reason: str | None = "Metrics were not calculated for this run."


class QualityMetrics(ApiModel):
    completeness: Metric = Field(default_factory=Metric)
    valid_row_rate: Metric = Field(default_factory=Metric)
    duplicate_id_rate: Metric = Field(default_factory=Metric)


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
    metrics: QualityMetrics = Field(default_factory=QualityMetrics)


Item = TypeVar("Item")


class Page(ApiModel, Generic[Item]):
    items: list[Item]
    total: int
    limit: int
    offset: int


class DatasetView(ApiModel):
    id: str
    name: str
    created_at: datetime


class VersionView(ApiModel):
    id: str
    dataset_id: str
    number: int
    parent_id: str | None
    file_id: str
    metadata: DatasetMetadata
    created_at: datetime


class StoredFinding(Finding):
    id: str
    check_run_id: str


class RunView(ApiModel):
    id: str
    version_id: str
    processing_status: Literal["running", "completed", "failed"]
    validation_status: Literal["passed", "failed", "not_available"]
    configuration: RuleSet
    reference_date: date
    implementation_version: str
    settings_snapshot: dict[str, JsonValue]
    baseline_id: str | None
    actor: str
    created_at: datetime
    completed_at: datetime | None
    error_code: str | None
    result: CheckResponse | None


class UploadResponse(ApiModel):
    metadata: DatasetMetadata
    persisted: Literal[True] = True
    dataset: DatasetView
    version: VersionView
    check_run: RunView


class AffectedRecord(ApiModel):
    record_number: int
    values: dict[str, str]


class AuditView(ApiModel):
    sequence: int
    dataset_id: str
    action: str
    entity_id: str
    actor: str
    created_at: datetime


ReviewValue = Literal["needs_correction", "accepted_as_is", "dismissed"]


class ReviewRequest(ApiModel):
    decision: ReviewValue = Field(examples=["needs_correction"])
    reason: str | None = Field(default=None, max_length=2000, examples=["Verified against the fictional source record."])

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    @model_validator(mode="after")
    def require_reason(self) -> Self:
        if self.decision in ("accepted_as_is", "dismissed") and self.reason is None:
            raise ValueError("Acceptance and dismissal require a nonblank reason.")
        return self


class ReviewView(ApiModel):
    id: str
    finding_id: str
    decision: ReviewValue
    reason: str | None
    actor: str
    created_at: datetime



