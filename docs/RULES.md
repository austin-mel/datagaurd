# Rules, metrics, and statistical analysis

[README](../README.md) · [Configuration](CONFIGURATION.md) · [Data dictionary](DATA_DICTIONARY.md)

## Rule configuration

Define your configuration with the strict Pydantic models in [rules.py](../src/rules.py). Use declared fields, finite numbers, unique rule IDs and required columns, and coherent prerequisites. Validate disabled rules too. Avoid duplicate YAML mapping keys, which the loader rejects. Correct configuration errors before starting the service.

| Ruleset field | Meaning |
| --- | --- |
| `schema_version` | Literal `1` |
| `name` | Nonblank revision family name |
| `structural_rule_id` | Unique structural check ID |
| `required_columns` | Unique nonblank headers; configured policy requires at least one |
| `rules` | Ordered list of discriminated rule objects |
| `identifier_column` | Optional explicit identifier; declare it in required columns |
| `identifier_policy` | `configured` (default) or `auto` |
| `statistics` | Optional analytical threshold configuration |

Give each rule an `id`, `kind`, `column`, and `explanation`. Set `severity` or `enabled` when you need values other than their defaults, `error` and `true`. Match IDs to `^[A-Z][A-Z0-9_]+$`, keep them distinct from the structural rule ID, and declare every rule column in `required_columns`.

## Rule kinds

| Kind | Additional fields | Evaluation |
| --- | --- | --- |
| `required` | None | Every row must contain a nonblank value |
| `unique` | None | All members of repeated nonmissing values fail |
| `pattern` | `pattern` | Portable full-value regex match |
| `allowed_values` | `values: string[]` | Exact case-sensitive membership; values must be unique and nonblank |
| `numeric` | Optional `generated_for` | Finite decimal parsing |
| `range` | `minimum`, `maximum`, `prerequisite` | Inclusive bounds, minimum no greater than maximum |
| `min` | `minimum`, `prerequisite` | Inclusive lower bound |
| `max` | `maximum`, `prerequisite` | Inclusive upper bound |
| `on_or_before_date` | `date`, optional `formats` | Inclusive upper calendar bound |
| `on_or_after_date` | `date`, optional `formats` | Inclusive lower calendar bound |
| `before_date` | `date`, optional `formats` | Exclusive upper calendar bound |
| `after_date` | `date`, optional `formats` | Exclusive lower calendar bound |
| `between_dates` | `start_date`, `end_date`, optional `formats` | Inclusive, ordered date interval |

Place a numeric parsing prerequisite before each bound rule on the same column. Enable the prerequisite whenever you enable its bound. If you generate a parser for a bound, reference that bound and match its enabled state and severity. Expect nonmissing nonnumeric values to fail the bound; the validator suppresses the generated parser's separate finding so the editor shows one constraint.

Add Required rules to reject missing values. Other checks generally evaluate nonmissing values and report skipped rows. If a required column is missing, inspect the structural failure before interpreting skipped column checks. Keep disabled rules valid even though the validator excludes them from execution.

## Complete YAML example

Save this configuration as a new YAML file and select it with `DATAGUARD_RULES_PATH`, or submit the equivalent JSON to `/rule-sets`:

```yaml
schema_version: 1
name: facility-scores
structural_rule_id: FACILITY_COLUMNS
required_columns: [facility_id, inspection_score]
identifier_policy: configured
identifier_column: facility_id
rules:
  - id: FACILITY_ID_REQUIRED
    kind: required
    column: facility_id
    explanation: Facility IDs must be present.
  - id: FACILITY_ID_UNIQUE
    kind: unique
    column: facility_id
    explanation: Facility IDs must be unique.
  - id: SCORE_NUMBER
    kind: numeric
    column: inspection_score
    explanation: Inspection scores must be numeric.
    generated_for: SCORE_RANGE
  - id: SCORE_RANGE
    kind: range
    column: inspection_score
    minimum: 0.0
    maximum: 100.0
    prerequisite: SCORE_NUMBER
    explanation: Inspection scores must be between zero and one hundred.
```

Add a Required rule if every row must have a score; this example permits missing scores. After creating a revision, assign its returned ID through `PUT /datasets/{id}/rule-set`, then check the desired version.

## Identifier resolution

Use the default [generic.yaml](../config/generic.yaml) for automatic identifier selection without domain-specific columns or rules. Set `identifier_column` to choose a column explicitly. With configured policy, you can also let the service infer the identifier from exactly one enabled unique column.

When using automatic selection, compare your headers with these priority groups after camelCase, space, and hyphen normalization:

1. `pk`, `primary_key`, `primarykey`, `primary_id`.
2. `id`, `uuid`, `guid`.
3. `record_id`, `row_id`, `unique_id`.
4. Headers ending in `_id`, `_uuid`, `_guid`, or `_pk`.

Use an explicit identifier when several headers match the first applicable priority group. The service selects only a single candidate and does not inspect row contents to break ties. A resolved automatic identifier receives reserved `GENERIC_ID_REQUIRED` and `GENERIC_ID_UNIQUE` checks. If resolution fails, read the skipped-check reason and treat the identifier-based metric as unavailable.

Distinguish the identifier column inside your data from the UUID that identifies the dataset resource.

## Number, date, and pattern syntax

Enter numbers with an optional sign, decimal notation, or exponent; the parser trims surrounding whitespace. Avoid NaN, infinity, currency symbols, grouping commas, and nonnumeric suffixes. Use real, zero-padded calendar dates in `%Y-%m-%d`, `%m/%d/%Y`, or `%d/%m/%Y` format; the default is ISO. Supply selected bounds as `YYYY-MM-DD`. Migrate retired `date`/`not_future` kinds before submitting those configurations.

Write portable regex patterns with 1–200 ASCII characters, no slash delimiters or flags, and a full-value match. Use ordinary/noncapturing groups, alternation, character classes, quantifiers, and ASCII shorthand classes. Avoid lookarounds, backreferences, inline flags, possessive quantifiers, nested classes, and set operations. Limit repetitions to 1,000,000. When extending syntax, keep Python's `rule_syntax.py` and the frontend's `ruleSyntax.ts` grammars aligned.

## Editor contract

Build editor requests with `DatasetRuleset`/`EditorRuleset`: supply `id`, `name`, `description`, `kind`, and `rules`, and preserve `backendConfiguration` when present. Include each rule's `id`, `enabled`, `column`, `type`, `condition`, `minimum`, and `maximum`, plus any date, severity, or backend metadata.

Map editor `regex` to backend `pattern`, `allowed` to `allowed_values`, and `date` to one of five date kinds. Enter allowed values as comma-separated, optionally quoted text; the converter builds the array. Let the converter generate numeric prerequisites and normalize editor IDs, then handle any ID-collision errors. The reverse projection hides generated parsers from the editor.

Create a custom ruleset before saving changes through the editor endpoint. Validate every rule, including disabled rules, and retain mandatory automatic identifier checks. Preserve the backend's identifier policy; client snapshots cannot replace it through this endpoint.

## Quality metrics

Use [metrics.py](../src/services/metrics.py) to interpret row-based quality calculations. Check `metric_semantics: row-based-v1` when reading results and inspect the separately recorded implementation version when reproducing a run.

| Metric | Numerator | Denominator |
| --- | --- | --- |
| `completeness` | Rows with all cells present | All rows |
| `valid_row_rate` | Rows with no error-severity validation finding | All rows |
| `uniqueness` | Rows with present, unique values in every enabled unique column, accounting for matching ignores | All rows |
| `duplicate_id_rate` | Nonmissing identifier rows belonging to repeated values, including every group member | Nonmissing identifier rows |

Calculate percentages as `100 × numerator / denominator`. Interpret lower duplicate-ID rates as better and distinguish them from uniqueness. Use the mean of available completeness, validity, and uniqueness percentages for the frontend overall score.

Treat a metric as unavailable when its denominator is zero or required structure is missing. Enable unique rules to calculate uniqueness and resolve an unambiguous identifier to calculate duplicate-ID rate. Count missing values against completeness and uniqueness, and review warnings separately from validity. When you ignore matching rule cells, expect validity/uniqueness to exclude those errors while completeness and raw identifier duplication continue reflecting actual data. Use finding-level decisions to annotate evidence without changing metrics.

## Statistical analysis

Use [statistics.py](../src/services/statistics.py) to inspect these analytical checks:

| Check | Behavior |
| --- | --- |
| `SCHEMA_COLUMNS` | Compare added/removed columns and normalized observed types with the parent version |
| `STAT_ROW_COUNT` | Absolute row-count change relative to the baseline; flag strictly above threshold |
| `STAT_IQR` | Per-column numeric values strictly outside Q1/Q3 fences; no baseline required |
| `STAT_MISSINGNESS` | Increase in missing percentage points against baseline |
| `STAT_CATEGORY_MIX` | Largest absolute category-share change for compatible text columns |

Review numeric IQR findings in every column, including mixed columns and identifiers. Supply enough usable samples, a nonzero IQR, and finite supported fences for IQR analysis. For missingness comparisons, provide enough rows in both versions; for category comparisons, provide enough nonmissing text values. Read `not_evaluated` reasons when a baseline, compatible types, or sufficient data is missing.

Use the parent source version as the baseline for comparative checks. Inspect each statistical warning's observed values, thresholds, and baseline ID before acting. Retrieve affected rows for IQR findings, and allow empty row membership for dataset-wide drift. Use complete membership when bounded samples do not cover your review needs. Configure thresholds and rule-specific overrides through [Configuration](CONFIGURATION.md).
