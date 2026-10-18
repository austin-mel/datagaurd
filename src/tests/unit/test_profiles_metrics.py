from decimal import Decimal

import pytest

from src.rules import RuleSet
from src.schemas import Finding, Metric
from src.services.metrics import percentage, quality_metrics
from src.services.profiling import finite, profile_dataset, quartile
from src.services.remediation import change_page, metric_delta
from src.schemas import RemediationRequest
from src.services.statistics import exceeds
from src.services.tabular import parse_dataset
from src.settings import Settings

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(("values", "quarter", "expected"), [
    ([5.0], 1, "5"), ([0., 10.], 1, "2.5"), ([0., 10.], 2, "5"),
    ([0., 10.], 3, "7.5"), ([-10., 0., 10., 20., 30.], 3, "20"),
    ([-1e308, 1e308], 2, "0"),
])
def test_quartile_interpolation(values: list[float], quarter: int, expected: str) -> None:
    assert quartile(values, quarter) == Decimal(expected)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_summary_values_become_null(value: float) -> None:
    assert finite(value) is None


def test_profiles_use_population_statistics_and_deterministic_ties(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"id,value\nA,1\nB,2\nC,3\nD,4\nE, \n", "data.csv", settings)
    profile = profile_dataset(parsed, simple_rules, top_count=2).columns[1]
    assert profile.observed_types == ["integer"]
    assert (profile.missing_count, profile.nonmissing_count, profile.distinct_count) == (1, 4, 4)
    assert profile.missing_percentage == 20
    assert profile.numeric_mean == profile.numeric_median == 2.5
    assert profile.numeric_stddev == pytest.approx(1.25 ** .5)
    assert (profile.numeric_q1, profile.numeric_q3) == (1.75, 3.25)
    assert [item.value for item in profile.top_categories] == ["1", "2"]
    assert [item.percentage for item in profile.category_frequencies] == [25] * 4


def test_empty_profile_has_no_fabricated_statistics(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"id,value\n", "data.csv", settings, allow_empty=True)
    for column in profile_dataset(parsed, simple_rules).columns:
        assert column.observed_types == []
        assert column.missing_percentage is None
        assert column.numeric_mean is column.numeric_median is column.numeric_stddev is None
        assert column.date_min is column.date_max is None
        assert column.top_categories == []


@pytest.mark.parametrize(("numerator", "denominator", "expected"), [(0, 1, 0), (1, 3, 100 / 3), (3, 3, 100)])
def test_percentage_has_explicit_evidence(numerator: int, denominator: int, expected: float) -> None:
    metric = percentage(numerator, denominator)
    assert metric.status == "available"
    assert metric.numerator == numerator and metric.denominator == denominator
    assert metric.percentage == pytest.approx(expected)
    assert metric.reason is None


def test_zero_denominator_is_unavailable() -> None:
    metric = percentage(0, 0)
    assert metric.status == "not_available"
    assert metric.percentage is None
    assert metric.denominator == 0
    assert metric.reason


def test_validity_counts_distinct_error_rows_and_excludes_warnings(settings: Settings, simple_rules: RuleSet) -> None:
    parsed = parse_dataset(b"id,value\nA,x\nB,x\nC,x\n", "data.csv", settings)
    finding = Finding(rule_id="RULE", column="value", severity="error", explanation="Bad value",
        observed_result={}, threshold={}, affected_count=1, record_samples=[], affected_record_numbers=[1])
    findings = [finding, finding.model_copy(update={"rule_id": "OTHER"}),
        finding.model_copy(update={"severity": "warning", "affected_record_numbers": [2]}),
        finding.model_copy(update={"category": "statistical", "affected_record_numbers": [3]})]
    metrics = quality_metrics(parsed, simple_rules, findings)
    assert metrics.valid_row_rate.numerator == 2
    assert metrics.valid_row_rate.denominator == 3
    assert metrics.completeness.percentage == 100


@pytest.mark.parametrize(("numerator", "denominator", "threshold", "expected"), [
    (5, 100, 5., False), (6, 100, 5., True), (4, 100, 5., False), (1, 10, 10., False),
])
def test_statistical_threshold_is_strict(numerator: int, denominator: int, threshold: float, expected: bool) -> None:
    assert exceeds(numerator, denominator, threshold) is expected


def test_metric_delta_requires_available_scores() -> None:
    assert metric_delta(percentage(1, 4), percentage(3, 4)) == 50
    assert metric_delta(percentage(3, 4), percentage(1, 4)) == -50
    assert metric_delta(Metric(), percentage(1, 1)) is None
    assert metric_delta(percentage(1, 1), Metric()) is None


def test_remediation_preview_pages_keep_order_and_count_unchanged_values() -> None:
    request = RemediationRequest.model_validate({"source_version_id": "source", "source_sha256": "a" * 64,
        "column": "value", "replacement": "new", "reason": "Verified",
        "records": [{"record_number": 3, "expected_value": "old"},
                    {"record_number": 1, "expected_value": "new"}, {"record_number": 2, "expected_value": "old"}]})
    page = change_page(request, 1, 1)
    assert page.total == 3 and page.limit == 1 and page.offset == 1
    assert page.items[0].record_number == 1
    assert not page.items[0].changed
    assert change_page(request, 10, 10).items == []
