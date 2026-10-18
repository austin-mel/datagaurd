from typing import Any

import pytest

from src.rules import RuleSet
from src.schemas import IgnoredCell, VersionReviewState
from src.services.cell_review import cell_groups, cell_value, ignored_members, rule_signature
from src.services.tabular import parse_dataset
from src.services.validation import check_dataset
from src.settings import Settings

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("value", "expected"), [("", None), (" ", " "), ("0", "0"), ("é", "é")])
def test_only_empty_cells_become_null(value: str, expected: str | None) -> None:
    assert cell_value(value) == expected


def test_signature_tracks_rule_semantics_not_editor_labels(simple_rules: RuleSet) -> None:
    rule = simple_rules.rules[0]
    signature = rule_signature(rule)
    assert len(signature) == 64
    assert rule_signature(rule.model_copy(update={"id": "RENAMED", "explanation": "New label"})) == signature
    for change in ({"column": "value"}, {"enabled": False}, {"severity": "warning"}):
        assert rule_signature(rule.model_copy(update=change)) != signature


def test_ignore_follows_original_row_identity_after_deletion(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"id,value\nA,\nB,ok\n", "data.csv", settings)
    decision = IgnoredCell(row_id=20, column="value", kind="violation", rule_id="VALUE_REQUIRED",
                           value=None, signature=rule_signature(simple_rules.rules[-1]))
    state = VersionReviewState(row_ids=[20, 30], ignored=[decision])
    assert ignored_members(parsed, simple_rules, state) == {("violation", "VALUE_REQUIRED", "value"): {1}}
    result = check_dataset(parsed, simple_rules, settings, review_state=state)
    assert result.validation_status == "passed"
    assert result.metrics.valid_row_rate.percentage == 100
    assert result.metrics.completeness.percentage == 50


@pytest.mark.parametrize("change", [
    {"row_id": 0}, {"row_id": 99}, {"column": "missing"}, {"value": "changed"},
    {"signature": "old rule"}, {"rule_id": "REMOVED_RULE"},
])
def test_stale_ignores_are_not_applied(settings: Settings, simple_rules: RuleSet, change: dict[str, Any]) -> None:
    parsed = parse_dataset(b"id,value\nA,\n", "data.csv", settings)
    decision = IgnoredCell.model_validate({"row_id": 1, "column": "value", "kind": "violation",
        "rule_id": "VALUE_REQUIRED", "value": None, "signature": rule_signature(simple_rules.rules[-1]), **change})
    assert ignored_members(parsed, simple_rules, VersionReviewState(ignored=[decision])) == {}


def test_deleted_row_ignore_does_not_transfer_to_new_position(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"id,value\nA,\n", "data.csv", settings)
    decision = IgnoredCell(row_id=1, column="value", kind="violation", rule_id="VALUE_REQUIRED",
                           value=None, signature=rule_signature(simple_rules.rules[-1]))
    assert ignored_members(parsed, simple_rules, VersionReviewState(row_ids=[2], ignored=[decision])) == {}


def test_statistical_ignore_uses_value_without_rule_signature(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"id,value\nA,999\n", "data.csv", settings)
    decision = IgnoredCell(row_id=1, column="value", kind="warning", rule_id="STAT_IQR",
                           value="999", signature=None)
    assert ignored_members(parsed, simple_rules, VersionReviewState(ignored=[decision, decision])) == {
        ("warning", "STAT_IQR", "value"): {1}}


def test_groups_include_all_members_beyond_samples_and_separate_values(settings: Settings, simple_rules: RuleSet) -> None:
    settings = settings.model_copy(update={"finding_sample_size": 1})
    parsed = parse_dataset(b"id,value\nA,\nA,\nB, \n", "data.csv", settings)
    result = check_dataset(parsed, simple_rules, settings)
    groups = cell_groups(parsed, result)
    by_value = {(group.ruleId, group.currentValue): group for group in groups}
    duplicate = by_value[("ID_UNIQUE", "A")]
    assert [(cell.rowNumber, cell.identifier) for cell in duplicate.cells] == [(1, "A"), (2, "A")]
    assert [cell.rowNumber for cell in by_value[("VALUE_REQUIRED", None)].cells] == [1, 2]
    assert [cell.rowNumber for cell in by_value[("VALUE_REQUIRED", " ")].cells] == [3]
    assert len({group.id for group in groups}) == len(groups)
    assert cell_groups(parsed, result) == groups


def test_structure_findings_do_not_create_cell_groups(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"unrelated\nx\n", "data.csv", settings)
    assert cell_groups(parsed, check_dataset(parsed, simple_rules, settings)) == []


def test_ignored_duplicate_affects_uniqueness_but_preserves_raw_duplicate_rate(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"id,value\nA,ok\nA,ok\n", "data.csv", settings)
    decision = IgnoredCell(row_id=1, column="id", kind="violation", rule_id="ID_UNIQUE",
                           value="A", signature=rule_signature(simple_rules.rules[1]))
    result = check_dataset(parsed, simple_rules, settings, review_state=VersionReviewState(ignored=[decision]))
    assert next(f for f in result.findings if f.rule_id == "ID_UNIQUE").affected_record_numbers == [2]
    assert result.metrics.uniqueness.percentage == 50
    assert result.metrics.valid_row_rate.percentage == 50
    assert result.metrics.duplicate_id_rate.percentage == 100
