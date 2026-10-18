# API Models and Stored Records

[README](../README.md) · [API reference](API.md) · [Rules](RULES.md)

Use [schemas.py](../src/schemas.py) for public models, [rules.py](../src/rules.py) for rule configuration, and [models.py](../src/models.py) for persistence. Submit only declared fields; API models reject unknown fields. Read dates and datetimes as strings and unavailable optional results as null. Use camelCase for workspace projections and snake_case for resource API models.

## Table of Contents

- [Identity and storage records](#identity-and-storage-records)
- [Dataset and version models](#dataset-and-version-models)
  - [DatasetMetadata](#datasetmetadata)
- [Profiles](#profiles)
- [Checks and evidence](#checks-and-evidence)
  - [CheckResponse](#checkresponse)
  - [RunView](#runview)
  - [Findings and analysis](#findings-and-analysis)
- [Metrics](#metrics)
- [Rule revisions](#rule-revisions)
- [Reviews and audit](#reviews-and-audit)
  - [Workspace review state](#workspace-review-state)
- [Remediations](#remediations)
- [Shared response envelopes](#shared-response-envelopes)

## Identity and storage records

| Record/table | Key and relationships | Stored content |
| --- | --- | --- |
| `Dataset` / `datasets` | UUID `id`; assigned `rule_set_id` | Display `name`, creation timestamp; names need not be unique |
| `RuleSetRecord` / `rule_sets` | UUID `id`; optional `parent_id`; unique name/revision pair | Immutable configuration JSON/hash, actor, timestamp |
| `DatasetVersion` / `dataset_versions` | UUID `id`; dataset/parent foreign keys; unique dataset/number and file ID | Version number, original filename, file/hash, metadata JSON, review-state JSON, creation timestamp |
| `CheckRun` / `check_runs` | UUID `id`; version, baseline, rule revision relationships | Processing status, pinned config/settings/review JSON, reference date, implementation version, result/error, actor/timestamps |
| `FindingRecord` / `findings` | UUID `id`; check run; unique run/position | Ordered finding payload JSON |
| `AuditEvent` / `audit_events` | Monotonic integer `sequence`; dataset foreign key | Action, entity ID, actor, timestamp, description |
| `ReviewDecision` / `review_decisions` | UUID `id`; finding foreign key | Append-only decision, optional reason, actor, timestamp |
| `Remediation` / `remediations` | UUID `id`; source/result versions and runs | Immutable proposal JSON, source hash, state, preview/decision/execution metadata |

Find source files under `files/<32-lowercase-hex>.<format>` within your storage directory. Distinguish these file IDs from dataset UUIDs. Read files through the storage service so it verifies their 64-character SHA-256 digest. Preserve version source bytes when updating review state; each run snapshots that state.

## Dataset and version models

| Model | Fields |
| --- | --- |
| `DatasetView` | `id`, `name`, `created_at`, `rule_set_id` |
| `VersionView` | `id`, `dataset_id`, integer `number`, nullable `parent_id`, `file_id`, `metadata`, `created_at` |
| `UploadResponse` | `metadata`, `persisted: true`, `dataset`, `version`, `check_run` |
| `UploadPolicy` | `extensions`, `max_upload_bytes`, `source_kind: file_upload`, `max_rows`, `max_columns`, `max_cells`, `max_decoded_bytes` |

### DatasetMetadata

| Field | Type/meaning |
| --- | --- |
| `original_filename` | Original display filename |
| `content_sha256` | Digest of the exact version bytes |
| `size_bytes` | Original byte count |
| `encoding` | Text encoding or null for binary formats |
| `format` | `csv`, `tsv`, `xlsx`, `parquet` |
| `sheet_name` | Selected workbook sheet or null |
| `row_count`, `column_count` | Parsed dimensions |
| `headers` | Ordered string array |
| `record_number_base` | `1`; first data record excludes the header |

## Profiles

Read `metadata` and `profile` from `ProfileResponse`. Use `DatasetProfile.row_count`, `column_count`, and `columns: ColumnProfile[]` to inspect your dataset dimensions and column summaries.

| ColumnProfile field | Meaning |
| --- | --- |
| `column`, `observed_types` | Header and observed `integer`, `number`, `date`, `text` types |
| `missing_count`, `nonmissing_count`, `missing_percentage` | Presence counts and percentage |
| `distinct_count` | Number of distinct populated values |
| `numeric_count`, `numeric_min`, `numeric_max` | Numeric population and extremes |
| `numeric_mean`, `numeric_median`, `numeric_stddev`, `numeric_q1`, `numeric_q3` | Numeric summaries; nullable when unavailable |
| `date_count`, `date_min`, `date_max` | Parsed date population and range |
| `top_categories`, `category_frequencies` | CategoryCount arrays; settings limit the top list |

Read `value`, `count`, and optional/nullable `percentage` from each `CategoryCount`. Distinguish a profile's distinct-value count from the row-based uniqueness metric.

## Checks and evidence

### CheckResponse

| Field | Meaning |
| --- | --- |
| `metadata`, `profile` | Parsed source description and profile |
| `metric_semantics` | `row-based-v1`; required on every completed result |
| `resolved_identifier_column` | Identifier header or null |
| `processing_status` | `completed` for a direct successful CheckResponse |
| `validation_status` | `passed` or `failed` |
| `findings`, `rule_results` | Finding evidence and per-rule outcomes |
| `metrics`, `analysis_results` | QualityMetrics and statistical/schema analysis outcomes |
| `reference_date`, `checked_at`, `actor` | Reproducibility date, UTC completion time, actor label |
| `implementation_version` | Validation implementation identity |
| `configuration`, `configuration_sha256` | Rule configuration and canonical digest |
| `settings_snapshot` | Effective recorded analysis/service settings |
| `baseline_id` | Parent source version used for comparative checks, or null |

### RunView

Read `id` and `version_id` to identify the attempt, `processing_status` and `validation_status` to interpret its state, and nullable `result: CheckResponse` for its evidence. Use `configuration`, `reference_date`, `implementation_version`, `settings_snapshot`, `baseline_id`, `actor`, and required `rule_set_id` to reproduce the check. Inspect `created_at`, `completed_at`, and `error_code` when diagnosing processing.

| State field | Values |
| --- | --- |
| `processing_status` | `running`, `completed`, `failed` |
| `validation_status` | `passed`, `failed`, `not_available` |
| RuleResult `status` | `passed`, `failed`, `skipped` |
| AnalysisResult `status` | `passed`, `review_required`, `not_evaluated` |

### Findings and analysis

| Model | Fields |
| --- | --- |
| `Finding` | `rule_id`, nullable `column`, `category`, nullable `baseline_id`, `severity`, `explanation`, `observed_result`, `threshold`, `affected_count`, `record_samples`, `affected_record_numbers` |
| `StoredFinding` | Finding plus persistent `id` and `check_run_id` |
| `RecordSample` | `record_number`, textual `value` |
| `AffectedRecord` | `record_number`, `values: { column: text }` |
| `RuleResult` | `rule_id`, nullable `column`, `status`, `evaluated_count`, `skipped_count`, nullable `reason` |
| `AnalysisResult` | `check_id`, nullable `column`, `category`, `status`, nullable `reason`, `observed_result`, `threshold`, nullable `baseline_id` |

Handle finding categories `validation`, `schema`, and `statistical`, analysis categories `schema` and `statistical`, and severities `error` and `warning`. Use `affected_record_numbers` for complete membership and `record_samples` for bounded examples. Allow empty membership for dataset-wide findings.

## Metrics

`QualityMetrics` contains `completeness`, `valid_row_rate`, `duplicate_id_rate`, and `uniqueness`. Each `Metric` has `status` (`available` or `not_available`), nullable `numerator`, `denominator`, `percentage`, and `reason`. See [Rules and metrics](RULES.md#quality-metrics) for exact denominators and ignore behavior.

## Rule revisions

Read `RuleSetView` for `id`, `name`, `revision`, nullable `parent_id`, `configuration`, `configuration_sha256`, `actor`, `created_at`, and `is_default`. Supply a nonempty `rule_set_id` in `RuleAssignment`. Consult [Rules](RULES.md) for configuration fields and rule discriminators.

## Reviews and audit

| Model | Fields and semantics |
| --- | --- |
| `ReviewRequest` | `decision`; optional `reason`, required for acceptance/dismissal |
| `ReviewView` | `id`, `finding_id`, `decision`, nullable `reason`, `actor`, `created_at` |
| `AuditView` | integer `sequence`, `dataset_id`, `action`, `entity_id`, `actor`, `created_at`, `description` |

Choose `needs_correction`, `accepted_as_is`, or `dismissed` for reviews. Inspect audit actions to trace dataset/version creation, rule assignment, checks, decisions, and remediations. Query the audit API for events beyond the frontend's five display titles.

### Workspace review state

| Model | Fields |
| --- | --- |
| `CellReviewGroup` | `id`, `column`, `ruleId`, `rule`, `kind: violation/warning`, `reason`, `currentValue: string/null`, `cells` |
| `ReviewedCell` | Positive `rowNumber`, nullable `identifier` |
| `CellReviewRequest` | `version`, `groupId`, positive `rowNumber`, `scope: one/all`, discriminated `action` |
| `VersionReviewState` | `row_ids`, `ignored`, nullable `pending_groups`, `review_changed`, `data_changed` |
| `IgnoredCell` | Stable `row_id`, `column`, `kind`, `rule_id`, nullable `value`, nullable rule `signature`, `reason` |

Submit `replace` with a string/null `value`, `delete-row`, or `ignore` with a `reason`. When inspecting stored review state, interpret an empty `row_ids` array as original one-based identities; deletions preserve surviving IDs. Update review state through cell-review actions rather than editing persistence fields directly.

Use `DatasetDetail` in service integrations to access the dataset, selected/latest version, latest run, assigned rules, change/pending flags, source metadata, recent events, review groups, identifier information, and ignored-cell count. For public workspace response fields, consult the [frontend dictionary](../../datagaurd.front-end/docs/DATA_DICTIONARY.md).

## Remediations

| Model | Fields |
| --- | --- |
| `RemediationRequest` | `action: replace_value`, `source_version_id`, `source_sha256`, `column`, `records`, `replacement`, `reason` |
| `ReplacementRecord` | Positive `record_number`, exact `expected_value` |
| `RecordChange` | `record_number`, `old_value`, `new_value`, boolean `changed` |
| `RemediationPreview` | `remediation`, 32-character `preview_token`, sampled `RecordChange[]` |
| `ApprovalRequest` | Latest `preview_token` |
| `RejectionRequest` | Nonblank `reason` |
| `ExecutionResponse` | `remediation`, corrected `version`, `check_run` |

`RemediationView` contains identity/source fields (`id`, `dataset_id`, `source_version_id`, `source_sha256`), proposal fields (`action`, `column`, `replacement`, `reason`, `selected_count`, `changed_count`), lifecycle (`status`, `actor`, `created_at`, `previewed_at`, `decision_actor`, `decided_at`, `rejection_reason`, `executed_at`, `error_code`), and result links (`source_check_run_id`, `result_version_id`, `check_run_id`). Lifecycle/result fields can be null before the corresponding step.

Track remediation progress with `proposed`, `approved`, `rejected`, `executing`, `executed`, and `failed`.

`RemediationComparison` contains `remediation`, `before_version`, `after_version`, nullable `before_check_run`, `after_check_run`, `checks_comparable`, nullable `comparison_reason`, `metric_change_percentage_points`, and paginated `changes`. Read nullable completeness, validity, and duplicate-ID-rate differences from `MetricChanges`; retrieve uniqueness from the individual check results.

## Shared response envelopes

| Model | Fields |
| --- | --- |
| `Page[T]` | `items`, `total`, `limit`, `offset` |
| `ErrorResponse` | `error: { code, message, details }` |
| `HealthResponse` | `status`, default `ok` |

Request 1–100 items per page (default 20) and start offset at 0. Read error details for structured context and server logs for tracebacks.
