from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from src.main import create_app
from src.models import DatasetVersion
from src.services.catalog import Catalog, require
from src.settings import PROJECT_ROOT, Settings


@pytest.fixture
def review_client(settings: Settings) -> Iterator[TestClient]:
    configured = settings.model_copy(update={"rules_path": PROJECT_ROOT / "config/generic.yaml"})
    with TestClient(create_app(configured)) as client:
        yield client


@pytest.fixture
def duplicate_dataset(review_client: TestClient) -> dict[str, Any]:
    response = review_client.post("/api/v1/datasets", files={"file": ("duplicates.csv", b"id,value\nA,one\nA,two\nB,three\n")})
    assert response.status_code == 201, response.text
    return dict(response.json())


def review_body(dataset: dict[str, Any], action: dict[str, Any], **changes: Any) -> dict[str, Any]:
    group = next(group for group in dataset["cellReview"] if group["ruleId"] == "GENERIC_ID_UNIQUE")
    return {"version": dataset["version"], "groupId": group["id"], "rowNumber": group["cells"][0]["rowNumber"],
            "scope": "one", "action": action, **changes}


@pytest.mark.parametrize(("changes", "code"), [
    ({"version": "v999"}, "not_found"), ({"groupId": "gone"}, "stale_finding"),
    ({"rowNumber": 3}, "stale_finding"),
    ({"action": {"type": "replace", "value": "A"}}, "no_changes"),
    ({"scope": "all", "action": {"type": "replace", "value": "C"}}, "bulk_unique_replacement"),
])
def test_invalid_reviews_leave_dataset_unchanged(review_client: TestClient, duplicate_dataset: dict[str, Any],
                                               changes: dict[str, Any], code: str) -> None:
    path = "/api/v1/datasets/" + duplicate_dataset["id"]
    body = {**review_body(duplicate_dataset, {"type": "ignore"}), **changes}
    response = review_client.post(path + "/cell-reviews", json=body)
    assert response.status_code in {404, 409, 422}
    assert response.json()["error"]["code"] == code
    assert review_client.get(path).json() == duplicate_dataset


def test_ignore_all_keeps_bytes_and_scores_until_revalidation(review_client: TestClient, duplicate_dataset: dict[str, Any]) -> None:
    path = "/api/v1/datasets/" + duplicate_dataset["id"]
    source = review_client.get(path + "/file", params={"version": "v1"}).content
    response = review_client.post(path + "/cell-reviews", json=review_body(duplicate_dataset,
        {"type": "ignore", "reason": " Expected duplicates "}, scope="all"))
    assert response.status_code == 200, response.text
    ignored = response.json()
    assert ignored["version"] == "v1" and ignored["reviewChangedSinceRun"]
    assert not ignored["dataChangedSinceRun"]
    assert ignored["cellReview"] == []
    assert ignored["qualityDimensions"] == duplicate_dataset["qualityDimensions"]
    assert review_client.get(path + "/file", params={"version": "v1"}).content == source
    validated = review_client.post(path + "/validation", json={"version": "v1"})
    assert validated.status_code == 200, validated.text
    assert validated.json()["validation"]["issues"] == []
    assert validated.json()["quality"] == 100
    assert "Ignored" in validated.json()["qualityNote"]


@pytest.mark.parametrize(("scope", "remaining"), [("one", 2), ("all", 1)])
def test_delete_rows_preserves_original_download_and_revalidates(review_client: TestClient, duplicate_dataset: dict[str, Any],
                                                               scope: str, remaining: int) -> None:
    path = "/api/v1/datasets/" + duplicate_dataset["id"]
    response = review_client.post(path + "/cell-reviews", json=review_body(duplicate_dataset, {"type": "delete-row"}, scope=scope))
    assert response.status_code == 200, response.text
    edited = response.json()
    assert edited["version"] == "v2" and edited["rowCount"] == remaining
    assert edited["dataChangedSinceRun"] and edited["validationPending"]
    assert review_client.get(path + "/file", params={"version": "v1"}).content == b"id,value\nA,one\nA,two\nB,three\n"
    current = review_client.get(path + "/file", params={"version": "v2"})
    assert current.content.startswith(b"\xef\xbb\xbf")
    validated = review_client.post(path + "/validation", json={"version": "v2"})
    assert validated.status_code == 200, validated.text
    assert validated.json()["quality"] == 100
    assert validated.json()["cellReview"] == []
    stale = review_client.post(path + "/cell-reviews", json=review_body(duplicate_dataset, {"type": "ignore"}))
    assert stale.status_code == 409 and stale.json()["error"]["code"] == "stale_version"


def test_delete_last_rows_supports_empty_snapshot(review_client: TestClient) -> None:
    uploaded = review_client.post("/api/v1/datasets", files={"file": ("all.csv", b"id\nA\nA\n")}).json()
    path = "/api/v1/datasets/" + uploaded["id"]
    edited = review_client.post(path + "/cell-reviews", json=review_body(uploaded, {"type": "delete-row"}, scope="all"))
    assert edited.status_code == 200, edited.text
    assert edited.json()["rowCount"] == 0
    result = review_client.post(path + "/validation", json={"version": edited.json()["version"]})
    assert result.status_code == 200, result.text
    assert result.json()["processingStatus"] == "completed"
    assert result.json()["quality"] is None


def test_unchanged_revalidation_does_not_append_versions_or_history(review_client: TestClient, duplicate_dataset: dict[str, Any]) -> None:
    path = "/api/v1/datasets/" + duplicate_dataset["id"]
    response = review_client.post(path + "/validation", json={"version": duplicate_dataset["version"]})
    assert response.status_code == 200
    assert response.json() == duplicate_dataset


def test_running_validation_blocks_edits_and_rule_changes(review_client: TestClient, duplicate_dataset: dict[str, Any]) -> None:
    assert isinstance(review_client.app, FastAPI)
    catalog: Catalog = review_client.app.state.catalog
    with catalog.database.write() as session:
        catalog.start_check(session, require(session, DatasetVersion, duplicate_dataset["versionId"]))
    path = "/api/v1/datasets/" + duplicate_dataset["id"]
    rules = {**duplicate_dataset["ruleset"], "kind": "custom"}
    responses = [
        review_client.post(path + "/validation", json={"version": duplicate_dataset["version"]}),
        review_client.post(path + "/cell-reviews", json=review_body(duplicate_dataset, {"type": "ignore"})),
        review_client.put(path + "/ruleset", json=rules),
    ]
    for response in responses:
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "validation_running"


def test_invalid_editor_rules_fail_without_changing_assignment(review_client: TestClient, duplicate_dataset: dict[str, Any]) -> None:
    path = "/api/v1/datasets/" + duplicate_dataset["id"]
    rules = duplicate_dataset["ruleset"]
    invalid = {**rules, "kind": "custom", "rules": [*rules["rules"], {
        "id": "NEW_RULE", "enabled": False, "column": "value", "type": "regex",
        "condition": "(?i)bad", "minimum": 0, "maximum": 100,
    }]}
    response = review_client.put(path + "/ruleset", json=invalid)
    assert response.status_code == 422 and response.json()["error"]["code"] == "invalid_rules"
    assert review_client.get(path).json() == duplicate_dataset
