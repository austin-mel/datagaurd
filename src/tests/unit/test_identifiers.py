import pytest

from src.rules import RuleSet, UniqueRule
from src.services.identifiers import identifier_column, resolved_rules

pytestmark = pytest.mark.unit


@pytest.fixture
def auto_rules() -> RuleSet:
    return RuleSet(schema_version=1, name="Automatic", structural_rule_id="COLUMNS",
                   required_columns=[], rules=[], identifier_policy="auto")


@pytest.mark.parametrize(("headers", "expected"), [
    (["customer_id", "id", "primaryKey"], "primaryKey"),
    (["row_id", "uuid"], "uuid"), (["order_id", "record ID"], "record ID"),
    (["name", "customerId"], "customerId"), ([" PRIMARY-KEY ", "id"], " PRIMARY-KEY "),
    (["name", "event_guid"], "event_guid"), (["id"], "id"),
])
def test_identifier_priority_and_header_normalization(auto_rules: RuleSet, headers: list[str], expected: str) -> None:
    assert identifier_column(auto_rules, headers) == (expected, None)


@pytest.mark.parametrize("headers", [["id", "uuid"], ["pk", "primary_key", "id"], ["order_id", "customer_id"]])
def test_ambiguity_does_not_fall_through(auto_rules: RuleSet, headers: list[str]) -> None:
    column, reason = identifier_column(auto_rules, headers)
    assert column is None
    assert reason and "Multiple possible primary keys" in reason


def test_no_identifier_reports_actionable_reason(auto_rules: RuleSet) -> None:
    assert identifier_column(auto_rules, ["name", "amount"])[0] is None
    assert "identifier_column" in (identifier_column(auto_rules, ["name"])[1] or "")


def test_explicit_identifier_precedes_inference(simple_rules: RuleSet) -> None:
    assert identifier_column(simple_rules, ["pk", "id"]) == ("id", None)
    # Missing configured columns are handled by structural validation, never silently replaced.
    assert identifier_column(simple_rules, ["pk"]) == ("id", None)


def test_configured_unique_rules_ignore_disabled_candidates(simple_rules: RuleSet) -> None:
    rules = simple_rules.model_copy(update={"identifier_column": None})
    assert identifier_column(rules, ["id", "value"]) == ("id", None)
    rules.rules.append(UniqueRule(id="OTHER_UNIQUE", kind="unique", column="value", explanation="Unique", enabled=False))
    assert identifier_column(rules, ["id", "value"]) == ("id", None)
    rules.rules[-1].enabled = True
    assert identifier_column(rules, ["id", "value"])[0] is None


def test_resolution_materializes_checks_without_mutating_configuration(auto_rules: RuleSet) -> None:
    before = auto_rules.model_dump()
    effective, reason = resolved_rules(auto_rules, ["id", "amount"])
    assert reason is None
    assert effective.identifier_column == "id"
    assert effective.identifier_policy == "configured"
    assert effective.required_columns == ["id"]
    assert [(rule.id, rule.kind, rule.column) for rule in effective.rules] == [
        ("GENERIC_ID_REQUIRED", "required", "id"), ("GENERIC_ID_UNIQUE", "unique", "id")]
    assert auto_rules.model_dump() == before
    assert resolved_rules(effective, ["id", "amount"])[0] == effective


def test_resolution_removes_disabled_rules(simple_rules: RuleSet) -> None:
    simple_rules.rules[-1].enabled = False
    effective, _ = resolved_rules(simple_rules, ["id", "value"])
    assert [rule.id for rule in effective.rules] == ["ID_REQUIRED", "ID_UNIQUE"]
    assert len(simple_rules.rules) == 3
