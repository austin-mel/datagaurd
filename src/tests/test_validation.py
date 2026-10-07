import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from src.rules import RuleSet, load_rules
from src.scripts.generate_fixtures import generate
from src.services.csv_parser import parse_csv
from src.services.validation import check_dataset
from src.settings import PROJECT_ROOT, Settings


@pytest.fixture
def rules(settings: Settings) -> RuleSet:
    return load_rules(settings.rules_path)


def test_full_manifest_exact_match(settings: Settings, rules: RuleSet) -> None:
    clean, dirty, manifest_bytes = generate()
    result = check_dataset(parse_csv(dirty, "dirty.csv", settings), rules, settings)
    manifest = json.loads(manifest_bytes)
    expected = {(entry["rule_id"], entry["record_number"]) for entry in manifest["errors"]}
    actual = {(finding.rule_id, number) for finding in result.findings for number in finding.affected_record_numbers}
    assert actual == expected
    assert len(actual) == 21
    assert len(result.findings) == 12
    assert result.validation_status == "failed"
    assert result.reference_date.isoformat() == manifest["reference_date"]
    clean_result = check_dataset(parse_csv(clean, "clean.csv", settings), rules, settings)
    assert clean_result.validation_status == "passed"
    assert not clean_result.findings
    assert all(outcome.status == "passed" for outcome in clean_result.rule_results)


def test_full_membership_and_prerequisites(settings: Settings, rules: RuleSet) -> None:
    settings = settings.model_copy(update={"finding_sample_size": 1})
    result = check_dataset(parse_csv(generate()[1], "dirty.csv", settings), rules, settings)
    duplicate = next(f for f in result.findings if f.rule_id == "FAC_ID_UNIQUE")
    assert duplicate.affected_record_numbers == [3, 4, 20]
    assert duplicate.affected_count == 3
    assert [sample.record_number for sample in duplicate.record_samples] == [3]
    score = next(r for r in result.rule_results if r.rule_id == "FAC_SCORE_RANGE")
    assert score.skipped_count == 4
    assert score.evaluated_count == 146
    assert score.reason and "FAC_SCORE_NUMERIC" in score.reason
    future = next(r for r in result.rule_results if r.rule_id == "FAC_DATE_NOT_FUTURE")
    assert future.skipped_count == 3


def test_structure_failure_and_skips(settings: Settings, rules: RuleSet) -> None:
    result = check_dataset(parse_csv(b"facility_name\nExample\n", "x.csv", settings), rules, settings)
    assert result.validation_status == "failed"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.rule_id == "FAC_REQUIRED_COLUMNS"
    assert finding.affected_count == 0
    assert finding.affected_record_numbers == []
    assert all(r.status == "skipped" and r.reason for r in result.rule_results if r.column not in (None, "facility_name"))


@pytest.mark.parametrize(("kind", "options", "values", "expected"), [
    ("required", {}, ["", " ", "a"], [1, 2]),
    ("unique", {}, ["001", "001", "1", ""], [1, 2]),
    ("pattern", {"pattern": "FAC-[0-9]{6}"}, ["FAC-000001", "FAC-1", "FAC-０００００１", ""], [2, 3]),
    ("allowed_values", {"values": ["Alder"]}, ["Alder", "alder", "Alder ", ""], [2, 3]),
    ("numeric", {}, ["0", "1.5", "1e2", "NaN", "Infinity", "1e999", "1_000", ""], [4, 5, 6, 7]),
    ("date", {"formats": ["%Y-%m-%d"]}, ["2024-02-29", "2026-02-29", "2026-1-01", "10/07/2026", ""], [2, 3, 4]),
])
def test_individual_rules(kind: str, options: dict[str, object], values: list[str], expected: list[int], settings: Settings) -> None:
    config = RuleSet.model_validate({
        "schema_version": 1, "name": "unit", "structural_rule_id": "STRUCTURE", "required_columns": ["x"],
        "rules": [{"id": "RULE", "kind": kind, "column": "x", "explanation": "Fixed explanation.", **options}],
    })
    content = ('x\n' + '\n'.join('"' + value + '"' for value in values)).encode()
    result = check_dataset(parse_csv(content, "x.csv", settings), config, settings)
    assert result.findings[0].affected_record_numbers == expected


def test_numeric_and_date_boundaries(settings: Settings, rules: RuleSet) -> None:
    content = (
        "facility_id,facility_name,county,facility_type,status,inspection_score,inspection_date\n"
        "FAC-000001,A,Alder,Clinic,Active,0,2026-10-07\n"
        "FAC-000002,B,Birch,Clinic,Active,100,2026-10-08\n"
        "FAC-000003,C,Cedar,Clinic,Active,100.01,2024-02-29\n"
    ).encode()
    result = check_dataset(parse_csv(content, "x.csv", settings), rules, settings)
    assert {(f.rule_id, tuple(f.affected_record_numbers)) for f in result.findings} == {
        ("FAC_DATE_NOT_FUTURE", (2,)), ("FAC_SCORE_RANGE", (3,))}
    later = settings.model_copy(update={"reference_date": date(2026, 10, 8)})
    assert len(check_dataset(parse_csv(content, "x.csv", later), rules, later).findings) == 1


def test_today_resolution_and_config_snapshot(settings: Settings, rules: RuleSet) -> None:
    result = check_dataset(parse_csv(generate()[0], "x.csv", settings), rules,
                           settings.model_copy(update={"reference_date": None}))
    assert result.reference_date == date.today()
    assert result.baseline_id is None
    assert result.configuration == rules
    assert result.configuration is not rules
    assert len(result.configuration_sha256) == 64
    assert result.implementation_version == "facilities-validation/1.0.0"


@pytest.mark.parametrize("endpoint", ["upload", "profile", "check"])
def test_endpoints_share_parser_errors(client: TestClient, endpoint: str) -> None:
    response = client.post(f"/datasets/{endpoint}", files={"file": ("bad.csv", b"a,a\n1,2", "text/csv")})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "duplicate_header"


@pytest.mark.parametrize(("fixture", "status"), [("facilities_clean.csv", "passed"), ("facilities_dirty.csv", "failed")])
def test_check_api_success_is_separate_from_validity(client: TestClient, fixture: str, status: str) -> None:
    content = (PROJECT_ROOT / "src/data" / fixture).read_bytes()
    response = client.post("/datasets/check", files={"file": (fixture, content, "text/csv")})
    assert response.status_code == 200
    result = response.json()
    assert result["processing_status"] == "completed"
    assert result["validation_status"] == status
    assert result["profile"]["row_count"] == 150

