import csv
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.rules import load_rules
from src.schemas import AnalysisResult, CheckResponse
from src.scripts.generate_statistical_fixtures import encode, generate
from src.services.tabular import ParsedDataset, parse_dataset
from src.services.profiling import profile_dataset
from src.services.validation import check_dataset
from src.settings import Settings


def rows() -> list[list[str]]:
    return list(csv.reader(io.StringIO(generate()["baseline.csv"].decode())))[1:]


def check(content: bytes, settings: Settings, baseline: bytes | None = None) -> CheckResponse:
    return check_dataset(parse_dataset(content, "current.csv", settings), load_rules(settings.rules_path), settings,
                         parse_dataset(baseline, "baseline.csv", settings) if baseline else None,
                         "baseline-id" if baseline else None)


def outcome(result: CheckResponse, check_id: str, column: str | None = None) -> AnalysisResult:
    return next(item for item in result.analysis_results if item.check_id == check_id and item.column == column)


def test_rich_profiles_and_finite_serialization(settings: Settings) -> None:
    content = encode([["001", "1", "2026-10-01"], ["002", "2", "2026-10-02"], ["003", "3", "bad"],
                      ["004", "4", ""], ["005", "NaN", "2026-02-30"], ["006", "Infinity", ""],
                      ["007", "", ""], ["008", "bad", ""]], ["id", "number", "day"])
    parsed = parse_dataset(content, "x.csv", settings)
    result = profile_dataset(parsed, load_rules(settings.rules_path), 2)
    number, day = result.columns[1:]
    assert number.numeric_count == 4
    assert number.numeric_mean == number.numeric_median == 2.5
    assert number.numeric_stddev == pytest.approx(1.118033988749895)
    assert (number.numeric_q1, number.numeric_q3) == (1.75, 3.25)
    assert number.missing_percentage == 12.5
    assert len(number.category_frequencies) == 7
    assert len(number.top_categories) == 2
    assert sum(item.percentage or 0 for item in number.category_frequencies) == pytest.approx(100)
    assert (day.date_count, day.date_min, day.date_max) == (2, date(2026, 10, 1), date(2026, 10, 2))
    assert parsed.records[0][0] == "001"
    extreme = check(encode([["1e308"], ["-1e308"]], ["value"]), settings)
    extreme.model_dump_json()
    assert extreme.profile.columns[0].numeric_mean == 0
    assert extreme.profile.columns[0].numeric_stddev == pytest.approx(1e308)


def test_valid_outlier_is_review_only_and_missing_baselines_are_explicit(settings: Settings) -> None:
    result = check(generate()["outlier.csv"], settings)
    assert result.validation_status == "passed"
    assert result.metrics.valid_row_rate.percentage == 100
    assert [(item.rule_id, item.category, item.affected_record_numbers) for item in result.findings] == [
        ("STAT_IQR", "statistical", [40])]
    assert all(item.status == "not_evaluated" and item.reason for item in result.analysis_results if item.check_id != "STAT_IQR")
    assert result.findings[0].baseline_id is None


@pytest.mark.parametrize(("last", "flag"), [("2", False), ("2.1", True)])
def test_iqr_fences_are_strict(settings: Settings, last: str, flag: bool) -> None:
    data = rows()[:20]
    values = ["0"] * 5 + ["1"] * 10 + ["2"] * 5
    values[-1] = last
    for row, value in zip(data, values, strict=True):
        row[5] = value
    result = outcome(check(encode(data), settings), "STAT_IQR", "inspection_score")
    assert result.observed_result["lower_fence"] == 0
    assert result.observed_result["upper_fence"] == 2
    assert result.status == ("review_required" if flag else "passed")


@pytest.mark.parametrize("size", [19, 20])
def test_iqr_insufficient_values_and_zero_spread(settings: Settings, size: int) -> None:
    data = rows()[:size]
    for row in data:
        row[5] = "50"
    result = outcome(check(encode(data), settings), "STAT_IQR", "inspection_score")
    assert result.status == "not_evaluated"
    assert result.reason == ("Insufficient usable numeric values." if size == 19 else "The interquartile range is zero.")


def test_shifted_and_unchanged_fixtures(settings: Settings) -> None:
    fixtures = generate()
    unchanged = check(fixtures["baseline.csv"], settings, fixtures["baseline.csv"])
    assert not unchanged.findings
    shifted = check(fixtures["shifted.csv"], settings, fixtures["baseline.csv"])
    assert shifted.validation_status == "passed"
    assert {(item.rule_id, item.column) for item in shifted.findings} == {
        ("STAT_ROW_COUNT", None), ("STAT_MISSINGNESS", "status"), ("STAT_CATEGORY_MIX", "county")}
    assert all(item.baseline_id == "baseline-id" and not item.affected_record_numbers for item in shifted.findings)
    configured = settings.model_copy(update={"row_count_change_percentage": 100,
                                             "missingness_increase_percentage_points": 100,
                                             "category_share_change_percentage_points": 100})
    assert not check(fixtures["shifted.csv"], configured, fixtures["baseline.csv"]).findings


def test_schema_changes_skip_incompatible_comparisons(settings: Settings) -> None:
    fixtures = generate()
    result = check(fixtures["schema.csv"], settings, fixtures["baseline.csv"])
    assert result.validation_status == "failed"
    schema = outcome(result, "SCHEMA_COLUMNS")
    assert schema.status == "review_required"
    assert schema.observed_result["added_columns"] == ["notes"]
    assert schema.observed_result["incompatible_columns"] == [
        {"column": "inspection_score", "baseline_types": ["number"], "current_types": ["text"]}]
    assert outcome(result, "STAT_MISSINGNESS", "inspection_score").reason == "The observed column types are incompatible."
    assert outcome(result, "STAT_CATEGORY_MIX", "notes").reason == "The column is absent from the baseline."
    renamed = check(b"other\n1\n", settings, b"extra\n1\n")
    assert outcome(renamed, "SCHEMA_COLUMNS").observed_result["removed_columns"] == ["extra"]
    assert renamed.validation_status == "failed"


@pytest.mark.parametrize(("count", "expected"), [(2, "passed"), (3, "review_required")])
def test_missingness_boundary(settings: Settings, count: int, expected: str) -> None:
    data = rows()
    for row in data[:count]:
        row[4] = ""
    result = check(encode(data), settings, generate()["baseline.csv"])
    assert outcome(result, "STAT_MISSINGNESS", "status").status == expected


@pytest.mark.parametrize(("count", "expected"), [(4, "passed"), (5, "review_required")])
def test_category_boundary_and_union(settings: Settings, count: int, expected: str) -> None:
    data = rows()
    for row in data[:count]:
        row[2] = "Cedar"
    result = check(encode(data), settings, generate()["baseline.csv"])
    assert outcome(result, "STAT_CATEGORY_MIX", "county").status == expected


@pytest.mark.parametrize(("size", "expected"), [(48, "passed"), (49, "review_required"), (32, "passed"), (31, "review_required")])
def test_volume_boundary(settings: Settings, size: int, expected: str) -> None:
    data = (rows() + rows())[:size]
    assert outcome(check(encode(data), settings, generate()["baseline.csv"]), "STAT_ROW_COUNT").status == expected


def test_small_empty_and_all_missing_baselines(settings: Settings) -> None:
    data = rows()[:19]
    result = check(encode(data), settings, generate()["baseline.csv"])
    assert outcome(result, "STAT_MISSINGNESS", "status").status == "not_evaluated"
    assert outcome(result, "STAT_CATEGORY_MIX", "county").status == "not_evaluated"
    baseline = parse_dataset(generate()["baseline.csv"], "x.csv", settings)
    empty = ParsedDataset(metadata=baseline.metadata.model_copy(update={"row_count": 0}), records=())
    result = check_dataset(baseline, load_rules(settings.rules_path), settings, empty, "empty")
    assert outcome(result, "STAT_ROW_COUNT").reason == "The baseline has zero records."
    data = rows()
    for row in data:
        row[4] = ""
    result = check(encode(data), settings, generate()["baseline.csv"])
    assert outcome(result, "STAT_MISSINGNESS", "status").status == "review_required"
    assert outcome(result, "STAT_CATEGORY_MIX", "status").status == "not_evaluated"


def test_baseline_links_reviews_and_stored_settings(client: TestClient) -> None:
    fixtures = generate()
    first = client.post("/datasets/upload", files={"file": ("base.csv", fixtures["baseline.csv"])}).json()
    response = client.post(f"/datasets/{first['dataset']['id']}/versions", files={"file": ("outlier.csv", fixtures["outlier.csv"])})
    assert response.status_code == 200, response.text
    second = response.json()
    run = second["check_run"]
    assert run["baseline_id"] == run["result"]["baseline_id"] == first["version"]["id"]
    assert run["settings_snapshot"]["iqr_multiplier"] == 1.5
    finding = client.get(f"/check-runs/{run['id']}/findings").json()["items"][0]
    assert finding["rule_id"] == "STAT_IQR"
    assert client.post(f"/findings/{finding['id']}/reviews", json={"decision": "accepted_as_is", "reason": "Valid extreme score."}).status_code == 201
    assert client.get(f"/check-runs/{run['id']}").json() == run
    assert client.get(f"/versions/{second['version']['id']}/file").content == fixtures["outlier.csv"]
    retry = client.post(f"/versions/{second['version']['id']}/check").json()
    assert retry["baseline_id"] == first["version"]["id"]
