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


DataFormat = Literal["csv", "tsv", "xlsx", "parquet"]


class DatasetMetadata(ApiModel):
    original_filename: str = Field(examples=["dataset.csv"])
    content_sha256: str
    size_bytes: int
    encoding: str | None = "utf-8"
    format: DataFormat = "csv"
    sheet_name: str | None = None
    row_count: int
    column_count: int
    headers: list[str]
    record_number_base: int = 1


class CategoryCount(ApiModel):
    value: str
    count: int
    percentage: float | None = None


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
    missing_percentage: float | None = None
    numeric_mean: float | None = None
    numeric_median: float | None = None
    numeric_stddev: float | None = None
    numeric_q1: float | None = None
    numeric_q3: float | None = None
    date_count: int = 0
    date_min: date | None = None
    date_max: date | None = None
    category_frequencies: list[CategoryCount] = Field(default_factory=list)


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
    category: Literal["validation", "schema", "statistical"] = "validation"
    baseline_id: str | None = None
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


class AnalysisResult(ApiModel):
    check_id: str
    column: str | None
    category: Literal["schema", "statistical"]
    status: Literal["passed", "review_required", "not_evaluated"]
    reason: str | None = None
    observed_result: dict[str, JsonValue]
    threshold: dict[str, JsonValue]
    baseline_id: str | None = None


class CheckResponse(ProfileResponse):
    resolved_identifier_column: str | None = None
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
    analysis_results: list[AnalysisResult] = Field(default_factory=list)


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
    rule_set_id: str


class RuleSetView(ApiModel):
    id: str
    name: str
    revision: int
    parent_id: str | None
    configuration: RuleSet
    configuration_sha256: str
    actor: str
    created_at: datetime
    is_default: bool


class RuleAssignment(ApiModel):
    rule_set_id: str = Field(min_length=1)


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
    rule_set_id: str | None = None


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


class ReplacementRecord(ApiModel):
    record_number: int = Field(ge=1, examples=[8])
    expected_value: str = Field(examples=["101"])


class RemediationRequest(ApiModel):
    action: Literal["replace_value"] = "replace_value"
    source_version_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    column: str = Field(min_length=1, examples=["inspection_score"])
    records: list[ReplacementRecord] = Field(min_length=1)
    replacement: str = Field(examples=["100"])
    reason: str = Field(min_length=1, max_length=2000, examples=["Corrected from the fictional source record."])

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A nonblank reason is required.")
        return value.strip()

    @field_validator("replacement")
    @classmethod
    def no_null_character(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Replacement values cannot contain a null character.")
        return value

    @model_validator(mode="after")
    def unique_records(self) -> Self:
        if len({record.record_number for record in self.records}) != len(self.records):
            raise ValueError("Select each record only once.")
        return self


RemediationStatus = Literal["proposed", "approved", "rejected", "executing", "executed", "failed"]


class RemediationView(ApiModel):
    id: str
    dataset_id: str
    source_version_id: str
    source_sha256: str
    action: Literal["replace_value"] = "replace_value"
    column: str
    replacement: str
    reason: str
    selected_count: int
    changed_count: int
    status: RemediationStatus
    actor: str
    created_at: datetime
    previewed_at: datetime | None
    decision_actor: str | None
    decided_at: datetime | None
    rejection_reason: str | None
    source_check_run_id: str | None
    result_version_id: str | None
    check_run_id: str | None
    executed_at: datetime | None
    error_code: str | None


class RecordChange(ApiModel):
    record_number: int
    old_value: str
    new_value: str
    changed: bool


class RemediationPreview(ApiModel):
    remediation: RemediationView
    preview_token: str
    samples: list[RecordChange]


class ApprovalRequest(ApiModel):
    preview_token: str = Field(min_length=32, max_length=32, description="Token returned by the latest preview.")


class RejectionRequest(ApiModel):
    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A nonblank reason is required.")
        return value.strip()


class ExecutionResponse(ApiModel):
    remediation: RemediationView
    version: VersionView
    check_run: RunView


class MetricChanges(ApiModel):
    completeness: float | None = None
    valid_row_rate: float | None = None
    duplicate_id_rate: float | None = None


class RemediationComparison(ApiModel):
    remediation: RemediationView
    before_version: VersionView
    after_version: VersionView
    before_check_run: RunView | None
    after_check_run: RunView
    checks_comparable: bool
    comparison_reason: str | None
    metric_change_percentage_points: MetricChanges
    changes: Page[RecordChange]



