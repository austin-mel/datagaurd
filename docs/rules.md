# Data formats and rules

## Accepted files

| Extension | Requirements |
| --- | --- |
| `.csv` | Comma-delimited UTF-8, with an optional BOM. |
| `.tsv` | Tab-delimited UTF-8, with an optional BOM; quoted tabs and newlines are supported. |
| `.xlsx` | A worksheet with text headers in row 1. Select `sheet_name` when multiple worksheets exist. Formulas and Excel error cells in the selected worksheet are rejected. |
| `.parquet` | Flat string, boolean, integer, floating-point, decimal, date, timestamp, time, or null columns, including dictionaries of these types. Nested and binary columns are rejected. |

Every file requires unique, nonblank headers and at least one record. Missing
values become empty strings for analysis. Text retains whitespace and leading
zeros. Native numbers use their stored values; spreadsheet display formats such
as padded numbers are not applied. Booleans become `true`/`false`; dates and times
use ISO representations. Text files preserve their original values.

Limits default to 10 MiB uploaded bytes, 50,000 records, 1,000 columns, 2,000,000
data cells, and 50 MiB expanded bytes. Excel archive expansion and Parquet column
sizes are checked before decoding; normalized text is also bounded. Set the
corresponding `DATAGUARD_MAX_*` values in the environment template to change limits.
Oversized inputs return 413; unsupported extensions/media types return 415;
invalid file contents return 422.

Original file bytes are immutable. Versions may use different supported formats.
Downloads use the original format. Corrections preserve unselected analyzed values
and are checked again before publication. Excel corrections preserve other sheets
but openpyxl may not retain every advanced workbook feature; keep the original
version for those features. Parquet corrections retain column types and reject
replacements that cannot round-trip exactly, such as `001` in an integer column.
An empty replacement clears a nullable nontext Parquet cell. Excel replacements
are literal text, including values starting with `=`.

## Dataset assignments

`POST /rule-sets` accepts a rule configuration and returns an immutable revision
with an `id`, revision number, parent revision, configuration hash, actor, and time.
Creating rules with the same name increments the revision. It does not change any
dataset assignment. List revisions with `GET /rule-sets`; `is_default` identifies
the revision used when an upload omits `rule_set_id`.

Each dataset has one assigned revision. Supply its ID in the upload form, or use
`PUT /datasets/{dataset_id}/rule-set` with `{"rule_set_id":"<id>"}`. Read the
assignment with `GET /datasets/{dataset_id}/rule-set`. Assignment changes are
audited. Future uploads, rechecks, and corrections use the assigned revision.
Historical runs keep their own rules, settings, reference date, and implementation
version. Reassignment alone does not run a check or rewrite earlier results.

The default configuration comes from `config/generic.yaml`. Changing that file
creates or selects a default revision at startup; existing datasets stay pinned.
Migration assigns older datasets their latest recorded rule snapshot, or the
default if no check exists. Old check snapshots remain readable.

## Generic default

The default has `identifier_policy: auto`, with empty `required_columns` and
`rules` lists. It accepts any dataset schema and adds required-value and uniqueness
checks for the selected primary key. It also retains general profiling and
statistical review. It does not impose any domain-specific formats, ranges, or
allowed values. `config/facilities.yaml` remains an optional example used by the
facility evaluation; it is not the application default.

Automatic selection uses these priorities:

1. `pk`, `primary_key`, `primarykey`, or `primary_id`.
2. `id`, `uuid`, or `guid`.
3. `record_id`, `row_id`, or `unique_id`.
4. A single column ending in `_id`, `_uuid`, `_guid`, or `_pk`.

Header matching ignores case and surrounding whitespace, accepts spaces/hyphens
as separators, and recognizes camel case such as `CustomerID`. The original header
and values are preserved. At the first matching priority, multiple candidates are
ambiguous. No candidate or ambiguous candidates cause both ID checks to be
`skipped`, with a reason; they do not establish key validity. The duplicate-ID
metric is then unavailable. Other checks continue, and validation may still pass.
Repeated foreign keys are allowed when a higher-priority primary key is selected.

The selected key appears in `resolved_identifier_column` in each result. It must
be nonblank and unique. Every member of a duplicate group is reported. Values are
compared exactly: `001` and `1`, or `A` and `a`, remain different identifiers.
Key checks are named `GENERIC_ID_REQUIRED` and `GENERIC_ID_UNIQUE`; these IDs are
reserved when automatic key checking is enabled.

To select a key explicitly, create and assign a rule set such as:

```json
{
  "schema_version": 1,
  "name": "order keys",
  "structural_rule_id": "ORDER_COLUMNS",
  "required_columns": ["order_id"],
  "rules": [],
  "identifier_policy": "auto",
  "identifier_column": "order_id"
}
```

This also fails validation if `order_id` is missing. The default key policy for
custom rule sets is `configured`, which runs only their declared rules and
requires nonempty column and rule lists. With that policy, `identifier_column`
selects the duplicate metric; add `required` and `unique` rules to enforce it.

## Dataset-specific rules

Example request body for `POST /rule-sets`:

```json
{
  "schema_version": 1,
  "name": "orders",
  "structural_rule_id": "ORDER_COLUMNS",
  "required_columns": ["order_id", "amount"],
  "identifier_column": "order_id",
  "rules": [
    {"id":"ORDER_ID_REQUIRED","kind":"required","column":"order_id","explanation":"Every order needs an ID."},
    {"id":"ORDER_ID_UNIQUE","kind":"unique","column":"order_id","explanation":"Order IDs must be unique."},
    {"id":"AMOUNT_NUMBER","kind":"numeric","column":"amount","explanation":"Amounts must be numeric."},
    {"id":"AMOUNT_RANGE","kind":"range","column":"amount","minimum":0,"maximum":100,"prerequisite":"AMOUNT_NUMBER","explanation":"Amounts must be between 0 and 100."}
  ],
  "statistics": {"row_count_change_percentage": 30}
}
```

Rule kinds: `required`, `unique`, `pattern`, `allowed_values`, `numeric`, `range`,
`date`, and `not_future`. Each rule has an ID, column, explanation, and optional
severity (`error` by default or `warning`). Rule columns must be declared in
`required_columns`. A range requires an earlier numeric rule on the same column;
`not_future` requires an earlier date rule. Date formats are `%Y-%m-%d`, `%m/%d/%Y`,
or `%d/%m/%Y`. Unknown fields, invalid regexes, duplicate IDs, and incoherent
prerequisites are rejected.

Missing values are handled by required rules. Other rules skip them. Numeric
validation rejects nonfinite values. Ranges and latest dates are inclusive.
Validation errors determine pass/fail; schema and statistical findings request
review without invalidating a row.

With the `configured` policy, `identifier_column` controls the duplicate-ID metric.
When omitted, a single unambiguous unique-rule column is used; otherwise the metric is unavailable.
Completeness measures populated cells covered by required rules; valid-row rate
counts records without validation errors. Zero denominators produce unavailable
metrics, not zero percent.

## Statistical settings

| Key | Default |
| --- | ---: |
| `statistical_min_samples` | 20 |
| `iqr_multiplier` | 1.5 |
| `missingness_increase_percentage_points` | 5 |
| `row_count_change_percentage` | 20 |
| `category_share_change_percentage_points` | 10 |

Omitting `statistics` snapshots the server's configured statistical settings at
revision creation. Supplying it uses the table defaults for omitted keys.
Numeric outliers fall strictly outside the IQR fences. Zero spread or insufficient
samples produces `not_evaluated`. Version comparisons flag incompatible schemas,
missingness increases, record-count changes, and category-share changes strictly
above their thresholds. Missing baselines are explicitly reported. Profiles include
finite numeric summaries, dates, missingness, and category frequencies.
