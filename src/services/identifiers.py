import re

from src.rules import RequiredRule, RuleSet, UniqueRule


def identifier_column(rules: RuleSet, headers: list[str]) -> tuple[str | None, str | None]:
    if rules.identifier_column:
        return rules.identifier_column, None
    if rules.identifier_policy == "configured":
        columns = {rule.column for rule in rules.rules if isinstance(rule, UniqueRule)}
        if len(columns) == 1:
            return next(iter(columns)), None
        return None, "No unambiguous identifier column is configured."
    normalized = {}
    for header in headers:
        name = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", header.strip())
        normalized[header] = re.sub(r"[\s-]+", "_", name).lower()
    groups = [
        {"pk", "primary_key", "primarykey", "primary_id"},
        {"id", "uuid", "guid"},
        {"record_id", "row_id", "unique_id"},
    ]
    candidates_by_priority = [[header for header, name in normalized.items() if name in group] for group in groups]
    candidates_by_priority.append([header for header, name in normalized.items()
                                   if name.endswith(("_id", "_uuid", "_guid", "_pk"))])
    for candidates in candidates_by_priority:
        if len(candidates) == 1:
            return candidates[0], None
        if candidates:
            return None, "Multiple possible primary keys: " + ", ".join(candidates) + ". Set identifier_column explicitly."
    return None, "No recognized primary key or ID column. Set identifier_column explicitly."


def resolved_rules(rules: RuleSet, headers: list[str]) -> tuple[RuleSet, str | None]:
    column, reason = identifier_column(rules, headers)
    if rules.identifier_policy != "auto" or column is None:
        return rules, reason
    checks = [*rules.rules,
              RequiredRule(id="GENERIC_ID_REQUIRED", kind="required", column=column,
                           explanation="Primary keys must be populated."),
              UniqueRule(id="GENERIC_ID_UNIQUE", kind="unique", column=column,
                         explanation="Primary keys must be unique; all duplicate group members are affected.")]
    return rules.model_copy(update={"identifier_column": column, "identifier_policy": "configured",
                                     "required_columns": list(dict.fromkeys([*rules.required_columns, column])),
                                     "rules": checks}), None
