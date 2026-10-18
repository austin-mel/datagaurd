# Ingestion and analysis guide

[README](../README.md) · [API reference](API.md) · [Rules](RULES.md)

## Supported files

Prepare your file using the requirements below. Consult [tabular.py](../src/services/tabular.py) when integrating or extending format support.

| Format | Extension | Requirements |
| --- | --- | --- |
| CSV | `.csv` | UTF-8, optional BOM, comma delimiter, valid quoted fields |
| TSV | `.tsv` | UTF-8, optional BOM, tab delimiter |
| Excel | `.xlsx` | Text headers and scalar values; select a sheet when multiple exist; formulas/errors unsupported |
| Parquet | `.parquet` | Flat supported scalar columns; nested and binary columns unsupported |

Use unique, nonblank headers and give each record the same number of fields as the header. Remove NUL characters and include at least one data row in an upload. After deleting all rows through cell review, you can retain an empty internal snapshot. Supply a MIME type that matches the extension, a supported alias, or generic octet-stream.

Expect the parser to normalize scalar values into text for analysis while the backend preserves your uploaded bytes separately. Use blank or whitespace-only cells to represent missing values; literal `null` remains text. Number records from 1 at the first data record, regardless of line breaks inside quoted CSV fields.

Keep your dataset within every configured limit. Defaults allow 100 MiB uploaded bytes, 200 MiB decoded bytes, 500,000 rows, 1,000 columns, and 2,000,000 cells. Account for expanded size when uploading compressed or binary formats. Read `/api/v1/upload-policy` for effective values.

## Analyze without saving a dataset

Run from the backend root against a running API. `curl.exe` avoids the legacy Windows PowerShell `curl` alias; use `curl` on macOS/Linux.

```powershell
curl.exe --fail-with-body -F "file=@src/data/facilities_dirty.csv" http://127.0.0.1:8000/datasets/profile
curl.exe --fail-with-body -F "file=@src/data/facilities_dirty.csv" http://127.0.0.1:8000/datasets/check
```

Use profile to retrieve metadata and column summaries without saving a dataset. Use check to also retrieve findings, rule outcomes, metrics, statistical analyses, and reproducibility fields. Omit `rule_set_id` to use the configured default, initially generic identifier validation. Select a saved facilities-specific ruleset when you want to evaluate facilities business rules.

HTTP 200 means processing completed. Inspect `validation_status`, each finding's category/severity, and each metric's availability rather than equating HTTP success with clean data.

## Upload and persist

```powershell
curl.exe --fail-with-body -F "file=@src/data/facilities_dirty.csv" http://127.0.0.1:8000/datasets/upload
```

Read `metadata`, `persisted: true`, `dataset`, `version`, and `check_run` from the response, and retain their IDs for later operations. Use `POST /api/v1/datasets` when you need a frontend projection with HTTP 201.

Treat each initial upload as a new dataset with a fresh UUID, even when you reuse a filename or content. Add `-F "rule_set_id=<revision-id>"` to choose a saved ruleset. For Excel, add `-F "sheet_name=Sheet1"` when necessary; omit sheet names for other formats.

If analysis fails after persistence, inspect the error details and saved catalog, then retry the saved version's check. Verify what the backend saved before repeating an upload.

## Append a version

```powershell
curl.exe --fail-with-body -F "file=@src/data/facilities_clean.csv" http://127.0.0.1:8000/datasets/DATASET_ID/versions
```

Replace `DATASET_ID` with the saved dataset UUID. The new version links to the latest committed version and uses the dataset's current assigned rules. Both original files remain available. Parent-version data supplies the baseline for comparative analyses.

## Check, inspect, and download

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/versions/VERSION_ID/check
Invoke-RestMethod http://127.0.0.1:8000/versions/VERSION_ID/check-runs
Invoke-RestMethod http://127.0.0.1:8000/check-runs/RUN_ID
Invoke-RestMethod http://127.0.0.1:8000/check-runs/RUN_ID/findings
Invoke-RestMethod http://127.0.0.1:8000/check-runs/RUN_ID/metrics
```

Replace uppercase placeholders with returned persistent IDs. The version check appends a new attempt. A failed processing attempt stays in history; it does not invalidate the saved source version.

Download to a new destination:

```powershell
curl.exe --fail-with-body --output downloaded-version.csv http://127.0.0.1:8000/versions/VERSION_ID/file
```

Use a filename extension matching `version.metadata.format`. Original downloads return the exact stored bytes after SHA-256 verification. Workspace downloads supply a human-readable versioned filename; lower-level downloads use the storage file ID in Content-Disposition.

## Interpret results

Read profiles for dimensions, missingness, observed types, distinct values, numeric/date summaries, and categories. Inspect findings for rule IDs, evidence, thresholds, severity, samples, and complete affected row numbers. When an analysis reports `not_evaluated`, read its reason: you may need a baseline, more usable values, compatible types, or supported numeric bounds.

Review the [rule and metric semantics](RULES.md) before comparing datasets. A missing metric is not zero, and statistical warnings do not establish an incorrect value. Use [Review and corrections](REVIEW.md) to record a decision or modify a verified source value.
