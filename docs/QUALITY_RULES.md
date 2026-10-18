# Quality rules guide

[README](../README.md) · [Workspace](WORKSPACE.md) · [Backend rule reference](../../datagaurd.back-end/docs/RULES.md)

## Create and save a custom ruleset

1. Open a dataset's quality-rules action from its overview or catalog.
2. Default rules are read-only. Select the create-custom action to copy them into an editable draft.
3. Name the ruleset, choose columns, add or edit rules, and enable the checks you want to run.
4. Save the rules. A failed save retains the draft in the dialog.
5. Select **Run Dataset Validation** on the overview to apply the assignment.

In live mode, save your changes to create and assign a backend rule revision while preserving historical check configurations. Validate every rule, including disabled rules, and keep the automatic required/unique checks enabled on the resolved identifier column. Refresh before coordinating edits with another user: ruleset saves lack a revision precondition, so concurrent saves can overwrite the assignment.

## Supported rules

| Editor type | Behavior | Example |
| --- | --- | --- |
| Required | Reject missing/blank values | Facility name must be present |
| Unique | Flag all duplicate members; uniqueness score also requires presence | One facility ID per row |
| Numeric | Require a finite numeric value | `12.5`, `-3`, `1e2` |
| Min / max | Inclusive lower and upper numeric bounds | Inspection score 0 through 100 |
| Minimum | Inclusive lower numeric bound | Capacity at least 0 |
| Maximum | Inclusive upper numeric bound | Score at most 100 |
| Regex | Match the complete value using the portable pattern grammar | `FAC-[0-9]{4}` |
| Allowed values | Exact, case-sensitive membership | `Active, Closed, Pending` |
| Date constraint | Compare a parsed date to selected calendar boundaries | On or before 2026-10-07 |

Add a Required rule to reject missing values; other value checks generally skip them. When interpreting uniqueness, count missing cells as nonunique even though Unique findings report duplicate nonmissing values. Add numeric bounds directly in the editor; it creates the backend parsing prerequisite and presents one visible bound rule.

## Allowed-value syntax

Separate values with commas. The editor trims unquoted values, so quote any value containing a comma or significant leading/trailing spaces. Double embedded quotes:

```text
Active, Closed, "North, East", "He said ""yes"""
```

Enter distinct, nonblank values and match their letter case exactly. When submitting a backend rule document, use an array of strings instead of this editor shorthand.

## Regular expressions

Enter a raw 1–200 character ASCII pattern without slash delimiters or flags. Match the entire value using literal characters, character classes, plain/noncapturing groups, alternation, ordinary quantifiers, and ASCII `\d`, `\w`, and `\s` shorthands. Avoid lookarounds, backreferences, inline flags, possessive quantifiers, nested classes, and set operations; the parser rejects them. Limit repetition counts to 1,000,000.

For example, `FAC-[0-9]{4}` accepts `FAC-0001` and rejects `prefix-FAC-0001`. When writing JSON instead of using the editor, escape backslashes: `"\\d{4}"` represents `\d{4}`.

## Date constraints

| Condition | Comparison |
| --- | --- |
| On or before selected date | Inclusive upper bound |
| On or after selected date | Inclusive lower bound |
| Before selected date | Exclusive upper bound |
| After selected date | Exclusive lower bound |
| Between two selected dates | Inclusive start and end; start must not follow end |

Choose fixed boundaries as valid `YYYY-MM-DD` dates. Use `%Y-%m-%d`, `%m/%d/%Y`, or `%d/%m/%Y` for source values; the default is ISO. Zero-pad each field and use valid calendar dates. Select an explicit cutoff instead of entering a relative “today” constraint.

## Score and warning interpretation

Review warnings even when your dataset has high quality scores. Error-severity findings reduce validity, while warning-severity rules and statistical warnings can require review without lowering that score. Configure statistical thresholds through backend settings or rules because the editor does not expose every analytical setting. Consult [backend Rules](../../datagaurd.back-end/docs/RULES.md) for configuration, identifier selection, metrics, and statistical checks.
