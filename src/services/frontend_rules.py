"""Conversion at the editor boundary; every rule is validated, even when disabled."""
import re
from typing import Literal

from pydantic import Field, JsonValue

from src.errors import InputError
from src.rules import NumericRule, Rule, RuleSet
from src.schemas import ApiModel, RuleSetView
from src.services.cell_review import rule_type
from src.services.identifiers import resolved_rules
from src.services.rule_syntax import allowed_values, format_allowed_values

DATE_CONDITIONS = {
    "on_or_before_date": "On or before selected date", "on_or_after_date": "On or after selected date",
    "before_date": "Before selected date", "after_date": "After selected date", "between_dates": "Between two selected dates",
}
FIXED_CONDITIONS = {"required": "Not empty", "unique": "One occurrence per value", "numeric": "Numeric value"}
RULE_LABELS = {"required": "Required", "unique": "Unique", "numeric": "Numeric", "regex": "Regex",
               "range": "Min / max", "min": "Minimum", "max": "Maximum", "allowed": "Allowed values", "date": "Date constraint"}


class EditorRule(ApiModel):
    id: str = Field(min_length=1)
    enabled: bool
    column: str = Field(min_length=1)
    type: Literal["required", "unique", "numeric", "regex", "range", "min", "max", "allowed", "date"]
    condition: str
    minimum: float | Literal[""]
    maximum: float | Literal[""]
    selectedDate: str | None = None
    endDate: str | None = None
    severity: Literal["error", "warning"] = "error"
    dateFormats: list[Literal["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"]] | None = None
    backendRule: Rule | None = None


class EditorRuleset(ApiModel):
    id: str
    name: str = Field(min_length=1)
    description: str = ""
    kind: Literal["default", "custom"]
    rules: list[EditorRule]
    backendConfiguration: RuleSet | None = None


def editor_catalog() -> dict[str, JsonValue]:
    options: list[JsonValue] = [
        {"value": kind, "label": label, "defaults": {
            "condition": FIXED_CONDITIONS.get(kind, DATE_CONDITIONS["on_or_before_date"] if kind == "date" else ""),
            "minimum": 0, "maximum": 100, "selectedDate": "", "endDate": "",
        }} for kind, label in RULE_LABELS.items()
    ]
    return {"defaultRuleType": "required", "ruleTypes": options, "dateConditions": list(DATE_CONDITIONS.values())}


def editor_ruleset(view: RuleSetView, headers: list[str]) -> EditorRuleset:
    effective, _ = resolved_rules(view.configuration, headers)
    # Retain disabled configured rules in the editor; materialize automatic ID checks independently of a run.
    configured = list(view.configuration.rules)
    if view.configuration.identifier_policy == "auto":
        configured.extend(rule for rule in effective.rules if rule.id in {"GENERIC_ID_REQUIRED", "GENERIC_ID_UNIQUE"})
    result: list[EditorRule] = []
    for rule in configured:
        if isinstance(rule, NumericRule) and rule.generated_for:
            continue
        data = rule.model_dump(mode="json")
        kind = rule_type(rule)
        condition = FIXED_CONDITIONS.get(kind, "")
        if kind == "regex":
            condition = data["pattern"]
        elif kind == "allowed":
            condition = format_allowed_values(data["values"])
        elif kind == "date":
            condition = DATE_CONDITIONS[data["kind"]]
        result.append(EditorRule.model_validate({
            "id": rule.id, "enabled": rule.enabled, "column": rule.column, "type": kind,
            "condition": condition, "minimum": data.get("minimum", 0), "maximum": data.get("maximum", 100),
            "selectedDate": data.get("date", data.get("start_date", "")), "endDate": data.get("end_date", ""),
            "severity": rule.severity, "dateFormats": data.get("formats"), "backendRule": data,
        }))
    return EditorRuleset(id=view.id, name=view.name, description=f"Assigned rule revision {view.revision}",
                        kind="default" if view.is_default else "custom", rules=result, backendConfiguration=view.configuration)


def backend_ruleset(editor: EditorRuleset, assigned: RuleSet, headers: list[str]) -> RuleSet:
    if editor.kind != "custom":
        raise InputError("default_rules_read_only", "Create a custom ruleset before saving changes.")
    identifiers = [rule.id for rule in editor.rules]
    if any(not identity.strip() for identity in identifiers) or len(set(identifiers)) != len(identifiers):
        raise InputError("invalid_rules", "Every rule must have a unique, nonblank ID.")
    effective, _ = resolved_rules(assigned, headers)
    automatic = {rule.id: rule for rule in effective.rules
                 if assigned.identifier_policy == "auto" and rule.id in {"GENERIC_ID_REQUIRED", "GENERIC_ID_UNIQUE"}}
    for identity, required in automatic.items():
        supplied = next((rule for rule in editor.rules if rule.id == identity), None)
        if supplied is None or not supplied.enabled or supplied.type != rule_type(required) or supplied.column != required.column or supplied.severity != required.severity:
            raise InputError("identifier_rules_required", "Retain the automatic required and unique checks for the resolved identifier.")
    ids = {rule.id: rule.id if re.fullmatch(r"[A-Z][A-Z0-9_]+", rule.id)
           else f"UI_{index}_" + re.sub(r"[^A-Za-z0-9_]", "_", rule.id).upper()
           for index, rule in enumerate(editor.rules)}
    if len(set(ids.values())) != len(ids) or assigned.structural_rule_id in ids.values():
        raise InputError("invalid_rules", "Rule IDs conflict after normalization.")
    used = {assigned.structural_rule_id, *ids.values()}
    result: list[dict[str, JsonValue]] = []
    columns = list(assigned.required_columns)
    for rule in editor.rules:
        # This check deliberately includes disabled rules.
        if rule.column not in headers:
            raise InputError("invalid_rules", f"Unknown column: {rule.column}")
        if rule.id in automatic:
            continue
        identity = ids[rule.id]
        common: dict[str, JsonValue] = {"id": identity, "column": rule.column, "enabled": rule.enabled,
            "severity": rule.severity, "explanation": f"{rule.column} must satisfy {rule.type}."}
        if rule.column not in columns:
            columns.append(rule.column)
        if rule.type in FIXED_CONDITIONS:
            result.append({**common, "kind": rule.type})
        elif rule.type == "regex":
            result.append({**common, "kind": "pattern", "pattern": rule.condition,
                           "explanation": f"{rule.column} must match {rule.condition}."})
        elif rule.type == "allowed":
            try:
                values = allowed_values(rule.condition)
            except ValueError as exc:
                raise InputError("invalid_rules", str(exc)) from exc
            result.append({**common, "kind": "allowed_values", "values": [value for value in values],
                           "explanation": f"{rule.column} must be one of: {', '.join(values)}."})
        elif rule.type in {"min", "max", "range"}:
            parser_id = identity + "_PARSE"
            while parser_id in used:
                parser_id += "_P"
            used.add(parser_id)
            result.append({**common, "kind": "numeric", "id": parser_id, "generated_for": identity})
            bound: dict[str, JsonValue] = {**common, "kind": rule.type, "prerequisite": parser_id}
            if rule.type != "max":
                bound["minimum"] = rule.minimum
            if rule.type != "min":
                bound["maximum"] = rule.maximum
            bound["explanation"] = f"{rule.column} must satisfy {rule.type}: " + (
                f"{rule.minimum} through {rule.maximum}." if rule.type == "range" else
                f"{rule.minimum if rule.type == 'min' else rule.maximum}.")
            result.append(bound)
        else:
            date_kind = next((kind for kind, label in DATE_CONDITIONS.items() if label == rule.condition), None)
            if date_kind is None:
                raise InputError("invalid_rules", "Select a supported date condition.")
            constraint: dict[str, JsonValue] = {**common, "kind": date_kind,
                "formats": [value for value in (rule.dateFormats or ["%Y-%m-%d"])],
                "explanation": f"{rule.column} must satisfy {rule.condition}: {rule.selectedDate}"
                    + (f" through {rule.endDate} (inclusive)." if date_kind == "between_dates" else ".")}
            if date_kind == "between_dates":
                constraint.update(start_date=rule.selectedDate, end_date=rule.endDate)
            else:
                constraint["date"] = rule.selectedDate
            result.append(constraint)
    # Backend identifier policy is authoritative; never trust a client snapshot to change it implicitly.
    document = assigned.model_dump(mode="json")
    document.update(name=editor.name, rules=result,
                    required_columns=columns if assigned.identifier_policy == "auto" else columns or headers)
    return RuleSet.model_validate(document)
