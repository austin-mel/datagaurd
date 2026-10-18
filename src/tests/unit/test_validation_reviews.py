import pytest

from src.rules import RuleSet
from src.schemas import IgnoredCell, VersionReviewState
from src.services.cell_review import cell_groups, rule_signature
from src.services.frontend_rules import backend_ruleset
from src.tests.unit.test_frontend_rules import editor, editor_rule
from src.services.tabular import parse_dataset
from src.services.validation import check_dataset
from src.settings import Settings

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("ignored_rows", [[21], [21, 22]])
def test_ignored_outliers_update_evidence_and_analysis(settings: Settings, simple_rules: RuleSet, ignored_rows: list[int]) -> None:
    content = ("id,value\n" + "".join(f"row-{index},{value}\n" for index, value in enumerate([*range(20), 1000, 2000], 1))).encode()
    parsed = parse_dataset(content, "data.csv", settings)
    state = VersionReviewState(ignored=[IgnoredCell(row_id=number, column="value", kind="warning", rule_id="STAT_IQR",
        value=parsed.records[number - 1][1], signature=None) for number in ignored_rows])
    result = check_dataset(parsed, simple_rules, settings, review_state=state)
    analysis = next(item for item in result.analysis_results if item.check_id == "STAT_IQR" and item.column == "value")
    assert analysis.observed_result["ignored_count"] == len(ignored_rows)
    assert analysis.observed_result["detected_outlier_count"] == 2
    assert analysis.observed_result["outlier_count"] == 2 - len(ignored_rows)
    findings = [finding for finding in result.findings if finding.rule_id == "STAT_IQR"]
    if len(ignored_rows) == 2:
        assert analysis.status == "passed" and findings == []
    else:
        assert analysis.status == "review_required"
        assert findings[0].affected_record_numbers == [22]
        assert [sample.record_number for sample in findings[0].record_samples] == [22]
    assert result.validation_status == "passed"


def test_generated_parser_and_constraint_share_ignore_decision(settings: Settings, simple_rules: RuleSet) -> None:
    rules = backend_ruleset(editor(editor_rule(type="range", minimum=0, maximum=10)), simple_rules, ["id", "value"])
    parsed = parse_dataset(b"id,value\nA,bad\nB,11\n", "data.csv", settings)
    baseline = check_dataset(parsed, rules, settings)
    assert [(finding.rule_id, finding.affected_record_numbers) for finding in baseline.findings] == [("VALUE_CHECK", [1, 2])]
    assert [group.ruleId for group in cell_groups(parsed, baseline)] == ["VALUE_CHECK", "VALUE_CHECK"]
    state = VersionReviewState(ignored=[IgnoredCell(row_id=1, column="value", kind="violation", rule_id="VALUE_CHECK",
        value="bad", signature=rule_signature(rules.rules[-1]))])
    result = check_dataset(parsed, rules, settings, review_state=state)
    assert [(finding.rule_id, finding.affected_record_numbers) for finding in result.findings] == [("VALUE_CHECK", [2])]
    parser = next(rule for rule in result.rule_results if rule.rule_id.endswith("_PARSE"))
    assert parser.status == "passed" and parser.skipped_count == 1


def test_overflowing_statistical_fences_are_explicitly_unavailable(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"id,value\nA,-1e308\nB,-1e308\nC,1e308\nD,1e308\n", "data.csv", settings)
    result = check_dataset(parsed, simple_rules, settings.model_copy(update={"statistical_min_samples": 4}))
    analysis = next(item for item in result.analysis_results if item.check_id == "STAT_IQR" and item.column == "value")
    assert analysis.status == "not_evaluated"
    assert analysis.reason and "finite numeric range" in analysis.reason
    assert 'Infinity' not in result.model_dump_json()
