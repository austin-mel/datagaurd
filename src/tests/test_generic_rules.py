from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.main import create_app
from src.rules import RuleSet, load_rules
from src.services.tabular import MEDIA_TYPES, parse_dataset
from src.services.validation import check_dataset
from src.settings import PROJECT_ROOT, Settings
from src.tests.test_formats import encode
from src.tests.test_remediation import approve, propose


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, storage_dir=tmp_path / "storage")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.mark.parametrize("header", ["id", "ID", "uuid", "GUID", "pk", "primary_key", "PrimaryKey",
                                     "record_id", "Unique ID", "order_id", "CustomerID", " employee-id "])
def test_generic_identifier_names(header: str, settings: Settings) -> None:
    rules = load_rules(settings.rules_path)
    content = encode("csv", [header, "description"], [["001", "first"], ["001", "second"], ["", "third"], ["1", "fourth"]])
    result = check_dataset(parse_dataset(content, "data.csv", settings), rules, settings)
    assert result.resolved_identifier_column == header
    assert result.validation_status == "failed"
    assert {finding.rule_id: finding.affected_record_numbers for finding in result.findings} == {
        "GENERIC_ID_REQUIRED": [3], "GENERIC_ID_UNIQUE": [1, 2]}
    assert result.metrics.completeness.percentage == 75
    assert result.metrics.valid_row_rate.percentage == 25
    assert result.metrics.duplicate_id_rate.percentage == pytest.approx(200 / 3)
    assert result.configuration == rules
    assert result.configuration.required_columns == []
    assert result.configuration.rules == []


@pytest.mark.parametrize("file_format", list(MEDIA_TYPES))
def test_generic_uploads_and_corrections(client: TestClient, file_format: str) -> None:
    content = encode(file_format, ["order_id", "amount"], [["001", "5000"], ["001", "-900"]])
    response = client.post("/datasets/upload", files={"file": ("orders." + file_format, content, MEDIA_TYPES[file_format])})
    assert response.status_code == 200, response.text
    saved = response.json()
    result = saved["check_run"]["result"]
    assert saved["check_run"]["configuration"]["name"] == "generic"
    assert result["resolved_identifier_column"] == "order_id"
    assert [item["rule_id"] for item in result["findings"]] == ["GENERIC_ID_UNIQUE"]
    identity = propose(client, saved, column="order_id", records=[{"record_number": 2, "expected_value": "001"}], replacement="002")
    approve(client, identity)
    corrected = client.post(f"/remediations/{identity}/execute")
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["check_run"]["validation_status"] == "passed"
    assert corrected.json()["check_run"]["result"]["resolved_identifier_column"] == "order_id"
    assert client.get(f"/versions/{saved['version']['id']}/file").content == content
    assert client.get(f"/check-runs/{saved['check_run']['id']}").json() == saved["check_run"]


@pytest.mark.parametrize(("headers", "selected"), [
    (["id", "customer_id"], "id"), (["primary_key", "id", "customer_id"], "primary_key"),
    (["record_id", "customer_id", "product_id"], "record_id"),
])
def test_primary_key_precedence_preserves_repeated_foreign_keys(settings: Settings, headers: list[str], selected: str) -> None:
    rows = [["A" if header == selected else "repeated" for header in headers],
            ["B" if header == selected else "repeated" for header in headers]]
    result = check_dataset(parse_dataset(encode("csv", headers, rows), "x.csv", settings), load_rules(settings.rules_path), settings)
    assert result.validation_status == "passed"
    assert result.resolved_identifier_column == selected
    assert not result.findings


@pytest.mark.parametrize("headers", [["customer_id", "product_id"], ["id", "ID"], ["name", "amount"]])
def test_ambiguous_or_missing_identifiers_are_explicitly_skipped(settings: Settings, headers: list[str]) -> None:
    result = check_dataset(parse_dataset(encode("csv", headers, [["A", "1"], ["A", "1"]]), "x.csv", settings),
                           load_rules(settings.rules_path), settings)
    assert result.validation_status == "passed"
    assert result.resolved_identifier_column is None
    assert result.metrics.duplicate_id_rate.status == "not_available"
    outcomes = [item for item in result.rule_results if item.rule_id.startswith("GENERIC_ID_")]
    assert len(outcomes) == 2
    assert all(item.status == "skipped" and item.reason and "identifier_column" in item.reason for item in outcomes)


def test_explicit_primary_key_and_missing_column(client: TestClient, settings: Settings) -> None:
    config = load_rules(settings.rules_path).model_dump(mode="json")
    config.update(name="Order keys", identifier_column="order_id", required_columns=["order_id"])
    registered = client.post("/rule-sets", json=config)
    assert registered.status_code == 201, registered.text
    identity = registered.json()["id"]
    response = client.post("/datasets/check", data={"rule_set_id": identity},
                           files={"file": ("x.csv", b"order_id,customer_id\nA,C\nB,C\n")})
    assert response.json()["validation_status"] == "passed"
    assert response.json()["resolved_identifier_column"] == "order_id"
    response = client.post("/datasets/check", data={"rule_set_id": identity}, files={"file": ("x.csv", b"id\nA\n")})
    assert response.json()["validation_status"] == "failed"
    assert response.json()["findings"][0]["observed_result"]["missing_columns"] == ["order_id"]


def test_identifiers_are_not_numeric_outlier_candidates(settings: Settings) -> None:
    content = encode("csv", ["id"], [[str(number)] for number in [*range(1, 20), 100000]])
    result = check_dataset(parse_dataset(content, "x.csv", settings), load_rules(settings.rules_path), settings)
    assert not result.findings
    assert next(item for item in result.analysis_results if item.check_id == "STAT_IQR").status == "not_evaluated"


def test_generic_revision_resolves_each_dataset_and_survives_restart(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        saved = [client.post("/datasets/upload", files={"file": ("x.csv", content)}).json()
                 for content in (b"id,name\n1,A\n2,B\n", b"employee_id,salary\nA,999999\nB,-1\n")]
        assert saved[0]["dataset"]["rule_set_id"] == saved[1]["dataset"]["rule_set_id"]
        assert [item["check_run"]["result"]["resolved_identifier_column"] for item in saved] == ["id", "employee_id"]
        assert all(item["check_run"]["validation_status"] == "passed" for item in saved)
        default = next(item for item in client.get("/rule-sets").json()["items"] if item["is_default"])
        assert default["name"] == "generic"
    with TestClient(create_app(settings)) as client:
        for item in saved:
            assert client.get(f"/check-runs/{item['check_run']['id']}").json() == item["check_run"]


def test_existing_facilities_assignment_is_not_rewritten(settings: Settings) -> None:
    old_settings = settings.model_copy(update={"rules_path": PROJECT_ROOT / "config" / "facilities.yaml"})
    with TestClient(create_app(old_settings)) as client:
        saved = client.post("/datasets/upload", files={"file": ("x.csv", b"id\n1\n")}).json()
        assert saved["check_run"]["validation_status"] == "failed"
    with TestClient(create_app(settings)) as client:
        default = next(item for item in client.get("/rule-sets").json()["items"] if item["is_default"])
        assert default["name"] == "generic"
        existing = client.get(f"/datasets/{saved['dataset']['id']}/rule-set").json()
        assert existing["name"] == "facilities"
        client.put(f"/datasets/{saved['dataset']['id']}/rule-set", json={"rule_set_id": default["id"]})
        assert client.post(f"/versions/{saved['version']['id']}/check").json()["validation_status"] == "passed"


def test_generic_configuration_rejects_reserved_ids_and_empty_custom_rules(settings: Settings) -> None:
    raw = load_rules(settings.rules_path).model_dump()
    for identity in ("GENERIC_ID_REQUIRED", "GENERIC_ID_UNIQUE"):
        with pytest.raises(ValidationError):
            RuleSet.model_validate({**raw, "structural_rule_id": identity})
    with pytest.raises(ValidationError):
        RuleSet.model_validate({**raw, "identifier_policy": "configured"})
