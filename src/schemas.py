from datetime import date, datetime
from typing import Annotated, Generic, Literal, Self, TypeVar

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
    encoding: str | None
    format: DataFormat
    sheet_name: str | None
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
    uniqueness: Metric = Field(default_factory=Metric)


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
    metric_semantics: Literal["row-based-v1"]
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
    metrics: QualityMetrics
    analysis_results: list[AnalysisResult]


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
    rule_set_id: str


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
    description: str = ""


class UploadPolicy(ApiModel):
    extensions: list[str]
    max_upload_bytes: int
    source_kind: Literal["file_upload"] = "file_upload"
    max_rows: int = 500_000
    max_columns: int = 1000
    max_cells: int = 2_000_000
    max_decoded_bytes: int = 200 * 1024 * 1024


class ReviewedCell(ApiModel):
    rowNumber: int = Field(ge=1)
    identifier: str | None


class CellReviewGroup(ApiModel):
    id: str
    column: str
    ruleId: str
    rule: str
    kind: Literal["violation", "warning"]
    reason: str
    currentValue: str | None
    cells: list[ReviewedCell]


class ReplaceCellAction(ApiModel):
    type: Literal["replace"]
    value: str | None

    @field_validator("value")
    @classmethod
    def valid_value(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("Enter a nonblank replacement without NUL characters, or use null.")
        return value


class DeleteRowAction(ApiModel):
    type: Literal["delete-row"]


class IgnoreCellAction(ApiModel):
    type: Literal["ignore"]
    reason: str = Field(default="", max_length=2000)


class CellReviewRequest(ApiModel):
    version: str = Field(min_length=1)
    groupId: str
    rowNumber: int = Field(ge=1)
    scope: Literal["one", "all"]
    action: Annotated[ReplaceCellAction | DeleteRowAction | IgnoreCellAction, Field(discriminator="type")]


class IgnoredCell(ApiModel):
    row_id: int
    column: str
    kind: Literal["violation", "warning"]
    rule_id: str
    value: str | None
    signature: str | None
    reason: str = ""


class VersionReviewState(ApiModel):
    # Empty row_ids means original one-based identities. Deletions retain original IDs.
    row_ids: list[int] = Field(default_factory=list)
    ignored: list[IgnoredCell] = Field(default_factory=list)
    pending_groups: list[CellReviewGroup] | None = None
    review_changed: bool = False
    data_changed: bool = False


class DatasetDetail(ApiModel):
    dataset: DatasetView
    selected_version: VersionView | None
    latest_version_id: str | None
    latest_run: RunView | None
    assigned_rules: RuleSetView
    rules_changed_since_run: bool
    source_kind: Literal["file_upload"] = "file_upload"
    uploaded_at: datetime | None
    uploaded_by: str | None
    source_filename: str | None = None
    source_format: DataFormat | None = None
    recent_events: list[AuditView]
    cell_review: list[CellReviewGroup] | None = None
    review_changed_since_run: bool = False
    data_changed_since_run: bool = False
    validation_pending: bool = False
    resolved_identifier_column: str | None = None
    identifier_reason: str | None = None
    ignored_cell_count: int = 0


class RevalidateRequest(ApiModel):
    source_version_id: str = Field(min_length=1)


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



