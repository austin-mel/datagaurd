# API reference

[README](../README.md) · [Data dictionary](DATA_DICTIONARY.md) · [Ingestion](INGESTION.md) · [Review](REVIEW.md)

## Connection and conventions

Send development requests to `http://127.0.0.1:8000`. Prefix workspace routes with `/api/v1`; call lower-level resource routes directly from the origin. Explore schemas through [Swagger UI](http://127.0.0.1:8000/docs), [ReDoc](http://127.0.0.1:8000/redoc), or [OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

Send JSON with `Content-Type: application/json`. For files, send multipart form data with `file`, optional `sheet_name`, and `rule_set_id` where the endpoint accepts it. Let your multipart client set the boundary. You can call these endpoints without credentials; the API does not enforce authentication.

Keep dataset, persistent version, run, finding, rule revision, and remediation IDs distinct. Supply display versions such as `v1` to workspace operations and persistent version IDs to lower-level version routes. Use IDs from API responses instead of deriving them from names.

## Health and documentation

| Method | Route | Result |
| --- | --- | --- |
| GET | `/health` | `{ "status": "ok" }`; process health |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |
| GET | `/openapi.json` | Generated endpoint/request/response schemas |

Use `/health` to check process health. Verify storage integrity and restored data separately through version downloads and history checks.

## Workspace adapter

Use these routes to integrate a frontend workspace. Read response fields in the [frontend data dictionary](../../datagaurd.front-end/docs/DATA_DICTIONARY.md) and route implementations in [frontend_routes.py](../src/frontend_routes.py).

| Method | Route | Request | Success |
| --- | --- | --- | --- |
| GET | `/api/v1/workspace` | None | 200, `{ datasets, ruleCatalog }`; complete current workspace |
| GET | `/api/v1/upload-policy` | None | 200, `UploadPolicy` |
| POST | `/api/v1/datasets` | Multipart `file`, optional `sheet_name` | 201, current `Dataset` projection |
| GET | `/api/v1/datasets/{dataset_id}` | None | 200, current `Dataset` |
| PUT | `/api/v1/datasets/{dataset_id}/ruleset` | `EditorRuleset` | 200, updated `Dataset` |
| POST | `/api/v1/datasets/{dataset_id}/validation` | `{ "version": "v1" }` | 200, updated `Dataset` |
| POST | `/api/v1/datasets/{dataset_id}/cell-reviews` | `CellReviewRequest` | 200, updated `Dataset` |
| GET | `/api/v1/datasets/{dataset_id}/file` | Required query `version=v1` | 200, source bytes with Content-Disposition |

Submit workspace rules with editor fields (`type`, `condition`, `minimum`, `maximum`). The backend converts them to its `kind`-discriminated configuration, preserves identifier policy, and generates numeric parser prerequisites. Follow the [editor contract](RULES.md#editor-contract) when building requests.

Request workspace revalidation when you have pending changes. Expect a new version for rule/review changes, reuse of an edited or failed version, or an unchanged response when no validation is necessary. Supply current version and group membership when editing cells.

## Ingestion and stateless analysis

Use these endpoints to persist uploads or analyze a file without saving it. Consult [routes.py](../src/routes.py) for the implementations.

| Method | Route | Request | Success |
| --- | --- | --- | --- |
| POST | `/datasets/upload` | Multipart `file`, optional `sheet_name`, optional `rule_set_id` | 200, `UploadResponse`; saves a dataset/version and runs a check |
| POST | `/datasets/profile` | Same multipart fields | 200, `ProfileResponse`; no dataset/version persisted |
| POST | `/datasets/check` | Same multipart fields | 200, `CheckResponse`; no dataset/version persisted |

Inspect `validation_status` after HTTP 200: processing can complete while validation finds invalid data. Use `/datasets/check` to analyze a file without creating persistent dataset history.

## Rules and assignments

Use these endpoints to create revisions and assign rules. Consult [rule_routes.py](../src/rule_routes.py) for the implementations.

| Method | Route | Request | Success |
| --- | --- | --- | --- |
| POST | `/rule-sets` | Backend `RuleSet` JSON | 201, immutable `RuleSetView` revision |
| GET | `/rule-sets` | Pagination | 200, `Page[RuleSetView]` |
| GET | `/rule-sets/{rule_set_id}` | None | 200, `RuleSetView` |
| GET | `/datasets/{dataset_id}/rule-set` | None | 200, assigned `RuleSetView` |
| PUT | `/datasets/{dataset_id}/rule-set` | `{ "rule_set_id": "<revision-id>" }` | 200, `DatasetView` |

Reuse a ruleset name to create its next revision, then update the dataset assignment explicitly. Use the singular lower-level `rule-set` route to assign an existing revision. Use the workspace `ruleset` route to create and assign a revision from editor input.

## Datasets, versions, and runs

Use these endpoints to inspect persisted records and append versions or checks. Consult [persistence_routes.py](../src/persistence_routes.py) for the implementations.

| Method | Route | Request | Success |
| --- | --- | --- | --- |
| GET | `/datasets` | Pagination | `Page[DatasetView]` |
| GET | `/datasets/{dataset_id}` | None | `DatasetView` |
| GET | `/datasets/{dataset_id}/versions` | Pagination | `Page[VersionView]` |
| POST | `/datasets/{dataset_id}/versions` | Multipart `file`, optional `sheet_name` | `UploadResponse`; append source version and check |
| GET | `/versions/{version_id}` | None | `VersionView` |
| GET | `/versions/{version_id}/file` | None | Original bytes; filename is the managed file ID |
| POST | `/versions/{version_id}/check` | No body | `RunView`; append a check attempt |
| GET | `/versions/{version_id}/check-runs` | Pagination | `Page[RunView]` |
| GET | `/check-runs/{run_id}` | None | `RunView`, including result or failure |
| GET | `/check-runs/{run_id}/metrics` | None | `QualityMetrics` |
| GET | `/datasets/{dataset_id}/audit` | Pagination | `Page[AuditView]` |

Expect HTTP 200 for successful requests in this table. Retry a saved version's check to append an attempt without reuploading or editing its source. Each new run snapshots the rules assigned at creation; inspect older runs to retrieve their original evidence.

## Findings and human decisions

| Method | Route | Request | Success |
| --- | --- | --- | --- |
| GET | `/check-runs/{run_id}/findings` | Pagination | 200, `Page[StoredFinding]` |
| GET | `/findings/{finding_id}` | None | 200, `StoredFinding` |
| GET | `/findings/{finding_id}/records` | Pagination | 200, `Page[AffectedRecord]` |
| POST | `/findings/{finding_id}/reviews` | `{ "decision": "accepted_as_is", "reason": "Verified at source" }` | 201, `ReviewView` |
| GET | `/findings/{finding_id}/reviews` | Pagination | 200, `Page[ReviewView]` |

Choose `needs_correction`, `accepted_as_is`, or `dismissed`. Include a nonblank reason for acceptance or dismissal, and limit reasons to 2,000 characters. Use these decisions to annotate evidence while preserving metrics, files, and findings.

## Approved remediations

Use these endpoints to propose, preview, approve, and execute exact replacements. Consult [remediation_routes.py](../src/remediation_routes.py) for the implementations.

| Method | Route | Request | Success |
| --- | --- | --- | --- |
| POST | `/remediations` | `RemediationRequest` | 201, `RemediationView` in proposed state |
| GET | `/datasets/{dataset_id}/remediations` | Pagination | 200, `Page[RemediationView]` |
| GET | `/remediations/{remediation_id}` | None | 200, proposal state/result IDs |
| GET | `/remediations/{remediation_id}/records` | Pagination | 200, `Page[RecordChange]` |
| POST | `/remediations/{remediation_id}/preview` | No body | 200, `RemediationPreview` and approval token |
| POST | `/remediations/{remediation_id}/approve` | `{ "preview_token": "<latest-32-character-token>" }` | 200, approved proposal |
| POST | `/remediations/{remediation_id}/reject` | `{ "reason": "<nonblank-reason>" }` | 200, rejected proposal |
| POST | `/remediations/{remediation_id}/execute` | No body | 200, `ExecutionResponse` |
| GET | `/remediations/{remediation_id}/comparison` | Pagination for changes | 200, `RemediationComparison` |

Build your proposal with this payload shape:

```json
{
  "action": "replace_value",
  "source_version_id": "<latest-version-id>",
  "source_sha256": "<64-lowercase-hex-characters-from-version-metadata>",
  "column": "inspection_score",
  "records": [{ "record_number": 8, "expected_value": "101" }],
  "replacement": "100",
  "reason": "Corrected against the source record."
}
```

Replace placeholders with response values. To change proposal input, create another proposal and repeat preview and approval. Use the newest preview token because each preview replaces the previous token. You can repeat execution of a completed proposal to retrieve its original result. Follow [Review and corrections](REVIEW.md) to recover from failures and interpret comparisons.

## Pagination

Set `limit` to 1–100 (default 20) and `offset` to a nonnegative value (default 0) on paginated routes. Read the result from this envelope:

```json
{ "items": [], "total": 0, "limit": 20, "offset": 0 }
```

Advance offset by the page size until you have read all items. Expect complete, unpaginated workspace projections. Use `/findings/{id}/records` to retrieve membership beyond bounded samples, and read remediation record pages in record-number order.

## Errors and retry behavior

Handle application, schema, database, and storage errors with this envelope:

```json
{
  "error": {
    "code": "stale_version",
    "message": "A newer version is available. Refresh before saving changes.",
    "details": {}
  }
}
```

Unmatched routes, method errors, or an upstream proxy can have a different body; inspect status and content type before parsing.

| Status | Typical codes | Client response |
| --- | --- | --- |
| 404 | `not_found` | Refresh IDs and verify resource ownership/relationship |
| 409 | `stale_version`, `stale_finding`, `validation_running`, `stale_source`, `source_hash_mismatch`, `old_value_mismatch`, `preview_required`, `invalid_transition` | Retrieve current state before reapplying the action |
| 413 | `upload_too_large`, `decoded_too_large`, resource-bound errors, `too_many_records` | Reduce input or adjust configured capacity |
| 415 | `unsupported_file_type`, `unsupported_encoding` | Supply a supported format and encoding |
| 422 | `invalid_request`, structural parsing errors, `invalid_rules`, `no_changes`, `incompatible_replacement` | Correct the request or source data |
| 500 | `internal_error` | Inspect server logs; response omits internal tracebacks |
| 503 | `database_unavailable`, `storage_unavailable`, `file_integrity_error`, `analysis_unavailable`, `execution_failed` | Inspect persisted state and logs before retrying |

Read sanitized validation locations/messages from `error.details.errors`. Retrieve the dataset, check, or remediation before retrying writes: the backend may commit a version before a storage or analysis failure. Account for the lack of general upload/write idempotency keys in your retry logic.
