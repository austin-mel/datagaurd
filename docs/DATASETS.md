# Upload Datasets and Review Cells

[README](../README.md) · [Workspace](WORKSPACE.md) · [Backend ingestion](../../datagaurd.back-end/docs/INGESTION.md)

Upload your files, download dataset versions, and review or correct flagged cells.

## Table of Contents

- [Upload a dataset](#upload-a-dataset)
- [Download a version](#download-a-version)
- [Review a flagged cell](#review-a-flagged-cell)
- [Ignore a finding](#ignore-a-finding)
- [Conflicts and limitations](#conflicts-and-limitations)

## Upload a dataset

Before uploading, connect to the backend and let the application load its upload policy.

1. Open **Datasets**, then **Connect a new data source**.
2. Choose or drag one `.csv`, `.tsv`, `.xlsx`, or `.parquet` file.
3. For a workbook with multiple worksheets, enter the exact worksheet name.
4. Select **Upload & validate**, then open the dataset returned in the catalog.

Check the live upload policy before choosing a file. Default limits allow 100 MiB uploaded bytes, 200 MiB decoded bytes, 500,000 rows, 1,000 columns, and 2,000,000 cells. The browser checks extension, empty files, and upload size; the backend also checks structure, decoded size, dimensions, and contents. Encode CSV/TSV as UTF-8 with an optional BOM, use unique nonblank headers, and include at least one data row. Replace Excel formulas/errors with values and flatten Parquet data to supported scalar columns before uploading.

Use the UI to create a new dataset; each upload receives a fresh UUID even if its filename and content match an existing upload. To append a file to an existing dataset, use the backend version API. The backend preserves your original source bytes. Review validation findings after a successful upload; findings describe data quality rather than a transport failure.

If the connection fails, inspect the catalog before uploading again: the server may already have saved the first request, and uploads do not have idempotency keys.

## Download a version

Open the overview and download the current version with its human-readable, versioned filename. Download an original upload to retrieve its exact bytes and format. After a cell edit, you receive a UTF-8 CSV snapshot even if you uploaded Excel or Parquet; the backend retains your original version. Use the backend version routes to download older versions.

## Review a flagged cell

Before editing, wait for active validation to finish and open a cell-review group from the completed check or pending review state.

1. Open a flagged value and verify the column, rule, current value, and selected row.
2. Choose a replacement, NULL, or row removal.
3. Review the before/after preview and match count.
4. Apply to one selected cell/row or all matches where allowed.
5. Run dataset validation when the edits are ready.

| Action | Result |
| --- | --- |
| Replace with custom input | Saves the supplied nonblank text; literal `null` remains text |
| Replace with NULL | Makes the value missing; it can still fail required/unique checks |
| Remove row | Deletes the entire selected record, including cells with no findings |
| Ignore finding | Leaves values intact and suppresses the selected finding membership |

Choose **All matches** to act on the same dataset version, column, finding, and exact current value, including matches outside your page or filters. Check the match count before saving. Correct values individually when the column has an enabled unique rule; the editor blocks shared replacements that could create duplicates. You can still remove or ignore matching rows/findings through their respective actions.

Run validation after saving replacements or deletions: each save creates an immutable version and marks it pending without running the check. Use the current group and version from the application. Interpret row numbers as one-based positions excluding the header, and recheck positions after deleting rows.

## Ignore a finding

1. Open the ignore action for a rule error or anomaly warning.
2. Select one finding or all matching findings.
3. Optionally enter the reason and select **Confirm ignore**.
4. Run validation to refresh error counts and quality scores.

Enter up to 2,000 characters to explain your decision, or leave the reason empty. The application removes ignored cells from review immediately and excludes matching ignored rule errors on the next check. Continue interpreting completeness as actual missing data. If you change a value or rule, review any finding that reappears: ignores match row identity, column, value, finding, and rule signature where applicable.

Use the backend's finding-level `accepted_as_is` or `dismissed` decisions when you want to annotate evidence without changing findings or metrics. Follow [Review and corrections](../../datagaurd.back-end/docs/REVIEW_DATASETS.md) for that workflow.

## Conflicts and limitations

If the source version or group changes, refresh, inspect the current version, and reselect your intended cell. The application rejects stale selections. Inspect saved versions through the backend for evidence; the UI provides no undo, dataset deletion, rename, version-history picker, or full-table spreadsheet editor. Use the backend API for additional history and approved remediations.
