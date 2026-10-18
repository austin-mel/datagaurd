# Workspace Types and API Projections

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Backend data dictionary](../../datagaurd.back-end/docs/DATA_DICTIONARY.md)

Use these types and field definitions when displaying datasets or sending workspace requests to the backend.

## Table of Contents

- [Conventions](#conventions)
- [Workspace and data source](#workspace-and-data-source)
- [Dataset](#dataset)
  - [State values](#state-values)
- [Quality and profiles](#quality-and-profiles)
- [Rulesets and editor catalog](#rulesets-and-editor-catalog)
- [Cell review](#cell-review)
- [Upload and download](#upload-and-download)

## Conventions

Use camelCase for frontend projections and snake_case for lower-level backend models. The workspace adapter returns frontend shapes. Handle absent optional fields, and display `null` results as unavailable. Read serialized dates/times as strings and recent-visit timestamps as epoch milliseconds.

Use the dataset UUID as its primary key. Distinguish display versions such as `v2` from persistent `versionId` and `latestRunId` values: each dataset can have multiple versions and each version can have multiple runs. Interpret row numbers as one-based data positions excluding headers, and refresh positions after deletions.

## Workspace and data source

Use [workspace.ts](../src/types/workspace.ts) when reading or constructing these workspace values:

| Field/type | Shape | Meaning |
| --- | --- | --- |
| `DatasetWorkspace.datasets` | `Dataset[]` | Complete catalog projection |
| `DatasetWorkspace.ruleCatalog` | `RuleEditorCatalog` | Supported editor choices and defaults |
| `DatasetDataSource` | `{ kind: 'api' }` | Backend selected |
| `DatasetDataSource` | `{ kind: 'seeded', reason }` | Samples selected; reason is `not-configured` or `backend-unavailable` |

Use one source for the entire workspace; do not mix API and sample records.

## Dataset

Use [dataset.ts](../src/types/dataset.ts) to implement these dataset fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `id`, `name` | string | Stable UUID and display name |
| `source`, `sourceIcon` | string, `'file'` | Source label and icon |
| `filename`, `downloadFilename` | optional string | Original display filename and suggested download filename |
| `uploadedAt`, `uploadedBy` | optional string | Original upload timestamp and actor |
| `history` | optional readonly `DatasetHistoryEvent[]` | Displayable audit events |
| `rowCount` | number | Rows in the selected version |
| `version`, `isCurrentVersion` | string, boolean | Version label and latest-version flag |
| `versionId`, `latestRunId` | optional string | Persistent backend identifiers |
| `status` | dataset status | User-facing state, listed below |
| `processingStatus` | processing status | Whether analysis is unstarted, active, completed, or failed |
| `processingError` | optional string | Failure information |
| `rulesChangedSinceRun` | boolean | Assigned rules differ from evaluated rules |
| `validationPending` | optional boolean | Initial validation or a check after edits is required |
| `reviewChangedSinceRun` | optional boolean | Review state has changed |
| `dataChangedSinceRun` | optional boolean | Source edits need validation |
| `quality` | number or null | Mean of available dimension percentages |
| `qualityDimensions` | readonly `QualityDimension[]` | Completeness, validity, uniqueness |
| `qualityNote` | string | Metric explanation, pending state, or global warnings |
| `lastValidatedAt` | string or null | Timestamp of available completed results |
| `columns` | readonly string[] | Ordered current headers |
| `columnProfiles` | readonly `ColumnProfile[]` or null | Profiles, or unavailable |
| `cellReview` | optional readonly `CellReviewGroup[]` or null | Complete grouped cell membership, or unavailable |
| `validation` | `{ checksRun, issues }` or null | Visible configured-check count and rule issues |
| `ruleset` | `DatasetRuleset` | Assigned editor rules |

### State values

| Type | Values |
| --- | --- |
| Dataset status | `needs-review`, `healthy`, `unvalidated`, `running`, `failed` |
| Processing status | `not_started`, `running`, `completed`, `failed` |
| Store status | `idle`, `loading`, `ready`, `error` |

The backend derives dataset status from processing, findings, and configured check count. Interpret `healthy` in the context of the rules you configured; it does not guarantee coverage of every business requirement.

## Quality and profiles

| Type | Fields |
| --- | --- |
| `QualityDimension` | `id`, `label`, `description`: string; `score`, `passed`, `total`: number or null |
| `ColumnProfile` | `name`: string; `observedTypes`: readonly type array; `missingCount`, `uniqueCount`: number; `warningCount`: number or null; `summary`: tagged union |
| `ValidationIssue` | `id`, `column`, `rule`, `message`: string; `affectedRows`: number |
| `DatasetHistoryEvent` | `id`, `occurredAt`, `description`: string; `title`: history title |

Handle observed types `text`, `integer`, `number`, `date`, and `boolean`. Read `uniqueCount` as a distinct-value count and `warningCount` as the number of distinct cells with statistical findings. Use quality dimensions for row-based uniqueness scores.

| Profile summary kind | Fields |
| --- | --- |
| `top-values` | `values: { value: string, count: number }[]` |
| `number-range` | `minimum`, `maximum`: number |
| `date-range` | `minimum`, `maximum`: string |

Display the history titles `Dataset uploaded`, `Validation ran`, `Ruleset saved`, `Dataset edited`, and `Findings ignored`. Retrieve the backend audit history when you need events beyond this UI projection.

## Rulesets and editor catalog

Use [ruleset.ts](../src/types/ruleset.ts) when building ruleset drafts and catalog choices:

| Type/field | Type | Meaning |
| --- | --- | --- |
| `DatasetRuleset.id`, `name`, `description` | string | Assignment identity and display metadata |
| `DatasetRuleset.kind` | `default` or `custom` | Default is read-only in the editor |
| `DatasetRuleset.rules` | readonly `QualityRule[]` | Editor rules, including disabled rules |
| `DatasetRuleset.backendConfiguration` | optional backend `RuleSet` | Preserved backend metadata |
| `QualityRule.id`, `column`, `condition` | string | Rule identity, column, and editor condition |
| `QualityRule.enabled` | boolean | Whether the rule executes |
| `QualityRule.type` | `required`, `unique`, `regex`, `range`, `min`, `max`, `allowed`, `date`, `numeric` | Editor discriminator |
| `QualityRule.minimum`, `maximum` | number or empty string | Bound values; empty string represents an incomplete input |
| `QualityRule.selectedDate`, `endDate` | optional string | ISO calendar boundaries |
| `QualityRule.severity` | optional `error` or `warning` | Error is the backend default |
| `QualityRule.dateFormats` | optional readonly format array | ISO, month/day/year, or day/month/year |
| `QualityRule.backendRule` | optional backend rule | Original underlying rule metadata |
| `RuleEditorCatalog.defaultRuleType` | `RuleType` | Type chosen for a new editor rule |
| `RuleEditorCatalog.ruleTypes` | readonly `{ value, label, defaults }[]` | Available types and condition/bound/date defaults |
| `RuleEditorCatalog.dateConditions` | readonly date-condition array | Five supported comparison labels |

See [Quality rules](QUALITY_RULES.md) for matching syntax and [backend Rules](../../datagaurd.back-end/docs/RULES.md) for the stored rule schema.

## Cell review

Build cell-review requests with the types in [cellReview.ts](../src/types/cellReview.ts):

| Field | Type | Meaning |
| --- | --- | --- |
| `CellReviewGroup.id` | string | Opaque group identity; use the returned value |
| `column`, `ruleId`, `rule`, `reason` | string | Column and finding metadata |
| `kind` | `violation` or `warning` | Rule violation or statistical warning |
| `currentValue` | string, number, boolean, or null | Shared flagged value; backend projects strings/null |
| `cells` | readonly `{ rowNumber, identifier }[]` | Complete membership; identifier can be null |
| Request `version` | string | Display version at selection time |
| Request `groupId`, `rowNumber` | string, number | Group and selected member |
| Request `scope` | `one` or `all` | Selected member or every member of that exact group |
| Request `action` | action union | Replacement, deletion, or ignore |

```json
{
  "version": "v1",
  "groupId": "group-id-from-response",
  "rowNumber": 2,
  "scope": "one",
  "action": { "type": "replace", "value": "FAC-9999" }
}
```

To create a missing value, delete a row, or ignore a finding, use `{ "type": "replace", "value": null }`, `{ "type": "delete-row" }`, or `{ "type": "ignore", "reason": "Verified at source" }` respectively.

## Upload and download

Use [datasetUpload.ts](../src/services/datasetUpload.ts), [backend.ts](../src/types/backend.ts), and the [repository contract](../src/services/datasetRepositoryContract.ts) to implement uploads and downloads:

| Shape | Fields |
| --- | --- |
| `DatasetUploadSelection` | Browser `file: File`, optional `sheetName: string` |
| `UploadPolicy` | `extensions: string[]`, `max_upload_bytes: number`; optional `source_kind`, `max_rows`, `max_columns`, `max_cells`, `max_decoded_bytes` |
| Download result | `filename: string`, `blob: Blob` |
| `DatasetRow` | Readonly mapping of column names to `string`, `number`, `boolean`, or `null` |

Pass `sheetName` to the upload repository; it sends multipart `sheet_name`. Handle API failures in the `{ "error": { "code", "message", "details" } }` envelope. Read status/message from `ApiError`, and handle connection availability through `BackendUnavailableError`.
