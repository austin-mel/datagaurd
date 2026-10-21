# Explore Your Data Quality Workspace

[README](../README.md) · [Datasets and cell review](DATASETS.md) · [Quality rules](QUALITY_RULES.md)

Navigate your datasets, interpret quality scores, and run validation after making changes.

## Table of Contents

- [Access and navigation](#access-and-navigation)
- [Live and sample data](#live-and-sample-data)
- [Read quality scores](#read-quality-scores)
- [Profiles, issues, and history](#profiles-issues-and-history)
- [Run validation](#run-validation)

## Access and navigation

Open [your local workspace](http://127.0.0.1:5173/dataguard/) without signing in. Use **Overview** to inspect one dataset and **Datasets** to search the catalog. Open a dataset to select it, or share its `/dataguard/?dataset=<uuid>` URL with someone using the same backend. Identify datasets by UUID because names and original filenames can repeat.

Return to Overview to resume your most recent available dataset. The application remembers three recent visits and otherwise selects the first dataset. Include a dataset UUID in the URL to open a specific record; if the record no longer exists, choose another dataset from the catalog.

## Live and sample data

Read the banner before working. Use `VITE_DATA_SOURCE=api` to connect to the backend and persist your work, or set `VITE_DATA_SOURCE=seeded` to explore synthetic samples in browser memory. Follow [Frontend Configuration and Troubleshooting](CONFIGURATION.md) to set the data source; the banner identifies the selected mode. You can download, edit rules, review cells, and validate samples; connect to the backend to upload files. Reloading or selecting Reconnect discards sample edits. If your live catalog is empty, upload a dataset or seed examples.

## Read quality scores

Interpret each score as a percentage of rows:

| Score | Meaning |
| --- | --- |
| Completeness | Percentage of rows with every cell present |
| Validity | Percentage of rows with no error-severity validation finding |
| Uniqueness | Percentage of rows with present, unique values in every enabled unique column |
| Overall quality | Arithmetic mean of the available dimension scores |

Count a row once in validity even if it fails several rules. Count every member of a duplicate group as nonunique, including the first occurrence, and count missing values as nonunique when the column has a unique rule. Review warnings separately because they do not reduce validity. Treat unavailable metrics as unavailable; the overall mean excludes them.

For example, a ten-row dataset with two incomplete rows has 80% completeness. If one row fails three error rules, validity is 90%. A duplicate value shared by two rows means both rows fail uniqueness for that column.

## Profiles, issues, and history

Use column profiles to inspect observed types, missing counts, distinct counts, and numeric/date ranges or top values. Read warning counts as distinct cells with statistical findings. Verify those cells against their source before deciding a value is wrong.

Read validation issues to identify failing rules and affected rows, then use cell review to inspect exact grouped membership before correcting values. Check the quality note for dataset-wide statistical warnings without editable cells. Use the backend API to retrieve complete statistical results and thresholds.

Use History to review uploads, completed validation, ruleset assignments, edits, and ignores. Query the backend audit API for additional events and full operation history.

## Run validation

Run validation when your selected dataset has pending changes or needs a check or retry.

1. Save a custom ruleset, edit a flagged cell, or ignore a finding.
2. Read the pending-change message; displayed prior results may be stale.
3. Select **Run Dataset Validation**.
4. Wait for processing to finish and inspect refreshed profiles, scores, findings, and history.

If the button is disabled, wait for the active operation to finish or check whether your data and rules already match the last completed run. Distinguish a processing failure from a completed check that found bad data: retry failed processing after resolving its cause, and review findings from completed checks even when scores are low.

If a connection fails during validation, the application attempts to retrieve the saved state. When it cannot confirm the result, refresh after restoring connectivity before deciding to retry.
