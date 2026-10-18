from datetime import datetime, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from src.errors import InputError
from src.rules import NumericRule, RangeRule, RuleSet
from src.schemas import RuleSetView
from src.services.frontend_rules import DATE_CONDITIONS, EditorRule, EditorRuleset, backend_ruleset, editor_catalog, editor_ruleset

pytestmark = pytest.mark.unit


def editor_rule(**changes: Any) -> EditorRule:
    return EditorRule.model_validate({"id": "VALUE_CHECK", "enabled": True, "column": "value", "type": "required",
        "condition": "Not empty", "minimum": 0, "maximum": 100, **changes})


def editor(*rules: EditorRule, **changes: Any) -> EditorRuleset:
    return EditorRuleset.model_validate({"id": "custom", "name": "Custom", "kind": "custom", "rules": list(rules), **changes})


def view(rules: RuleSet) -> RuleSetView:
    return RuleSetView(id="revision-1", name=rules.name, revision=1, parent_id=None, configuration=rules,
                       configuration_sha256="a" * 64, actor="tester", created_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
                       is_default=False)


@pytest.mark.parametrize(("kind", "changes", "backend_kind"), [
    ("required", {}, "required"), ("unique", {}, "unique"), ("numeric", {}, "numeric"),
    ("regex", {"condition": r"[A-Z]+\d{2}"}, "pattern"),
    ("allowed", {"condition": 'open, "a,b", "say ""hi"""'}, "allowed_values"),
    ("min", {"minimum": -5}, "min"), ("max", {"maximum": 10}, "max"),
    ("range", {"minimum": -5, "maximum": 10}, "range"),
    *[("date", {"condition": label, "selectedDate": "2026-01-01", "endDate": "2026-12-31",
                "dateFormats": ["%d/%m/%Y"]}, kind) for kind, label in DATE_CONDITIONS.items()],
])
def test_every_editor_type_round_trips(simple_rules: RuleSet, kind: str, changes: dict[str, Any], backend_kind: str) -> None:
    original = editor_rule(type=kind, severity="warning", **changes)
    converted = backend_ruleset(editor(original), simple_rules, ["id", "value"])
    target = next(rule for rule in converted.rules if rule.id == original.id)
    assert target.kind == backend_kind
    assert target.severity == "warning"
    round_trip = editor_ruleset(view(converted), ["id", "value"])
    assert len(round_trip.rules) == 1  # Generated numeric prerequisites stay out of the editor.
    restored = round_trip.rules[0]
    assert restored.type == kind
    assert restored.severity == "warning"
    assert backend_ruleset(round_trip, converted, ["id", "value"]) == converted


def test_generated_numeric_parser_avoids_collisions_and_preserves_disabled_state(simple_rules: RuleSet) -> None:
    converted = backend_ruleset(editor(editor_rule(type="range", enabled=False), editor_rule(id="VALUE_CHECK_PARSE")),
                                simple_rules, ["id", "value"])
    parser, bound, required = converted.rules
    assert isinstance(parser, NumericRule)
    assert isinstance(bound, RangeRule)
    assert parser.id == "VALUE_CHECK_PARSE_P"
    assert parser.generated_for == bound.id
    assert bound.prerequisite == parser.id
    assert not parser.enabled and not bound.enabled
    assert required.id == "VALUE_CHECK_PARSE"
    assert not editor_ruleset(view(converted), ["id", "value"]).rules[0].enabled


@pytest.mark.parametrize(("rules", "kind", "code"), [
    ([editor_rule()], "default", "default_rules_read_only"),
    ([editor_rule(), editor_rule()], "custom", "invalid_rules"),
    ([editor_rule(id=" ")], "custom", "invalid_rules"),
    ([editor_rule(id="COLUMNS")], "custom", "invalid_rules"),
    ([editor_rule(id="a-b"), editor_rule(id="UI_0_A_B")], "custom", "invalid_rules"),
    ([editor_rule(column="missing", enabled=False)], "custom", "invalid_rules"),
    ([editor_rule(type="allowed", condition="a,a")], "custom", "invalid_rules"),
    ([editor_rule(type="date", condition="Yesterday")], "custom", "invalid_rules"),
])
def test_editor_rejects_invalid_or_read_only_changes(simple_rules: RuleSet, rules: list[EditorRule], kind: str, code: str) -> None:
    with pytest.raises(InputError) as caught:
        backend_ruleset(editor(*rules, kind=kind), simple_rules, ["id", "value"])
    assert caught.value.code == code


@pytest.mark.parametrize("rule", [
    editor_rule(type="regex", condition="(?i)test", enabled=False),
    editor_rule(type="range", minimum=10, maximum=5),
    editor_rule(type="min", minimum=""),
    editor_rule(type="max", maximum=float("inf")),
    editor_rule(type="date", condition=DATE_CONDITIONS["before_date"], selectedDate="2026-02-30"),
    editor_rule(type="date", condition=DATE_CONDITIONS["between_dates"], selectedDate="2026-02-02", endDate="2026-01-01"),
])
def test_even_disabled_rules_must_validate(simple_rules: RuleSet, rule: EditorRule) -> None:
    with pytest.raises(ValidationError):
        backend_ruleset(editor(rule), simple_rules, ["id", "value"])


@pytest.mark.parametrize("change", ["remove", "disable", "column", "type", "severity"])
def test_automatic_identifier_protection(change: str) -> None:
    assigned = RuleSet(schema_version=1, name="Auto", structural_rule_id="COLUMNS", required_columns=[],
                       rules=[], identifier_policy="auto")
    editable = editor_ruleset(view(assigned), ["id", "value"])
    editable.kind = "custom"
    if change == "remove":
        editable.rules.pop()
    elif change == "disable":
        editable.rules[0].enabled = False
    elif change == "column":
        editable.rules[0].column = "value"
    elif change == "type":
        editable.rules[0].type = "numeric"
    else:
        editable.rules[0].severity = "warning"
    with pytest.raises(InputError) as caught:
        backend_ruleset(editable, assigned, ["id", "value"])
    assert caught.value.code == "identifier_rules_required"


def test_client_configuration_cannot_override_identifier_policy(simple_rules: RuleSet) -> None:
    assigned = RuleSet(schema_version=1, name="Auto", structural_rule_id="COLUMNS", required_columns=[],
                       rules=[], identifier_policy="auto")
    editable = editor_ruleset(view(assigned), ["id", "value"])
    editable.kind = "custom"
    editable.backendConfiguration = simple_rules
    result = backend_ruleset(editable, assigned, ["id", "value"])
    assert result.identifier_policy == "auto"
    assert result.identifier_column is None
    assert result.rules == []
    assert assigned.name == "Auto"


def test_editor_catalog_has_unique_supported_types() -> None:
    catalog = editor_catalog()
    options = catalog["ruleTypes"]
    assert isinstance(options, list)
    types = [option["value"] for option in options if isinstance(option, dict)]
    assert len(types) == len(set(types)) == 9
    assert set(types) == {"required", "unique", "numeric", "regex", "range", "min", "max", "allowed", "date"}
    assert catalog["defaultRuleType"] == "required"
    assert catalog["dateConditions"] == list(DATE_CONDITIONS.values())
