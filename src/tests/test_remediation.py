import csv
import io
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.errors import InputError
from src.main import create_app
from src.rules import load_rules
from src.schemas import ApprovalRequest, RemediationRequest
from src.scripts.generate_fixtures import generate
from src.scripts.generate_statistical_fixtures import generate as statistical_fixtures
from src.services.catalog import Catalog
from src.services.tabular import parse_dataset
from src.services.remediation import Remediations
from src.services.validation import check_dataset
from src.settings import Settings
from src.tests.test_persistence import upload


def body(saved: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {"source_version_id": saved["version"]["id"], "source_sha256": saved["metadata"]["content_sha256"],
            "column": "inspection_score", "records": [{"record_number": 8, "expected_value": "101"}],
            "replacement": "100", "reason": "Verified fictional source.", **changes}


def propose(client: TestClient, saved: dict[str, Any], **changes: Any) -> str:
    response = client.post("/remediations", json=body(saved, **changes))
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def approve(client: TestClient, identity: str) -> None:
    preview = client.post(f"/remediations/{identity}/preview")
    assert preview.status_code == 200, preview.text
    response = client.post(f"/remediations/{identity}/approve", json={"preview_token": preview.json()["preview_token"]})
    assert response.status_code == 200, response.text


def test_correction_workflow_survives_restart(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        saved = upload(client)
        identity = propose(client, saved)
        approve(client, identity)
        response = client.post(f"/remediations/{identity}/execute")
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["remediation"]["status"] == "executed"
        assert result["version"]["parent_id"] == saved["version"]["id"]
        assert result["check_run"]["baseline_id"] == saved["version"]["id"]
        assert result["check_run"]["result"]["metrics"]["valid_row_rate"]["numerator"] == 131
        comparison = client.get(f"/remediations/{identity}/comparison").json()
        assert comparison["checks_comparable"]
        assert comparison["metric_change_percentage_points"]["valid_row_rate"] == pytest.approx(2 / 3)
        before = client.get(f"/versions/{saved['version']['id']}/file").content
        after = client.get(f"/versions/{result['version']['id']}/file").content
        old_rows = list(csv.reader(io.StringIO(before.decode())))
        new_rows = list(csv.reader(io.StringIO(after.decode())))
        old_rows[8][5] = "100"
        assert old_rows == new_rows
        assert before == generate()[1]
    with TestClient(create_app(settings)) as client:
        assert client.post(f"/remediations/{identity}/execute").json() == result
        assert client.get(f"/datasets/{saved['dataset']['id']}/versions").json()["total"] == 2
        assert client.get(f"/datasets/{saved['dataset']['id']}/remediations").json()["items"] == [result["remediation"]]
        assert client.get(f"/remediations/{identity}/comparison").json() == comparison
        events = client.get(f"/datasets/{saved['dataset']['id']}/audit?limit=100").json()["items"]
        transitions = [event["action"] for event in events if event["entity_id"] == identity]
        assert transitions == ["remediation_proposed", "remediation_previewed", "remediation_approved",
                               "remediation_executing", "remediation_executed"]
        retry = client.post(f"/versions/{result['version']['id']}/check").json()
        assert client.get(f"/remediations/{identity}/comparison").json()["after_check_run"]["id"] == retry["id"]


def test_preview_approval_and_rejection_enforce_scope(client: TestClient) -> None:
    saved = upload(client)
    identity = propose(client, saved)
    assert client.post(f"/remediations/{identity}/execute").status_code == 409
    assert client.post(f"/remediations/{identity}/approve", json={"preview_token": "0" * 32}).status_code == 409
    first = client.post(f"/remediations/{identity}/preview").json()
    second = client.post(f"/remediations/{identity}/preview").json()
    assert first["samples"] == [{"record_number": 8, "old_value": "101", "new_value": "100", "changed": True}]
    assert first["preview_token"] != second["preview_token"]
    assert client.post(f"/remediations/{identity}/approve", json={"preview_token": first["preview_token"]}).status_code == 409
    assert client.post(f"/remediations/{identity}/reject", json={"reason": " "}).status_code == 422
    rejected = client.post(f"/remediations/{identity}/reject", json={"reason": "Wrong source."}).json()
    assert rejected["status"] == "rejected" and rejected["decision_actor"] == "local_operator"
    assert client.post(f"/remediations/{identity}/execute").status_code == 409
    assert client.post(f"/remediations/{identity}/approve", json={"preview_token": second["preview_token"]}).status_code == 409
    assert client.patch(f"/remediations/{identity}", json={"replacement": "90"}).status_code == 405
    assert client.get(f"/datasets/{saved['dataset']['id']}/versions").json()["total"] == 1


@pytest.mark.parametrize(("changes", "status"), [
    ({"source_sha256": "0" * 64}, 409),
    ({"records": [{"record_number": 8, "expected_value": "wrong"}]}, 409),
    ({"records": [{"record_number": 151, "expected_value": "101"}]}, 422),
    ({"records": [{"record_number": 0, "expected_value": "101"}]}, 422),
    ({"records": [{"record_number": 8, "expected_value": "101"}] * 2}, 422),
    ({"records": []}, 422), ({"column": "missing"}, 422), ({"reason": " "}, 422),
    ({"replacement": "101"}, 422), ({"replacement": "\x00"}, 422),
    ({"actor": "someone_else"}, 422), ({"action": "delete_records"}, 422),
])
def test_invalid_proposals(client: TestClient, changes: dict[str, Any], status: int) -> None:
    saved = upload(client)
    assert client.post("/remediations", json=body(saved, **changes)).status_code == status
    assert client.get(f"/datasets/{saved['dataset']['id']}/remediations").json()["total"] == 0


def test_preview_pagination_and_exact_string_replacement(settings: Settings) -> None:
    settings = settings.model_copy(update={"finding_sample_size": 1})
    with TestClient(create_app(settings)) as client:
        saved = upload(client)
        identity = propose(client, saved, column="facility_name", replacement='  New, "name"\r\n001  ',
                           records=[{"record_number": 6, "expected_value": " \t "}, {"record_number": 5, "expected_value": ""}])
        preview = client.post(f"/remediations/{identity}/preview").json()
        assert preview["remediation"]["changed_count"] == 2
        assert len(preview["samples"]) == 1
        assert client.get(f"/remediations/{identity}/records?limit=1&offset=1").json()["items"][0]["record_number"] == 6
        approve(client, identity)
        result = client.post(f"/remediations/{identity}/execute").json()
        content = client.get(f"/versions/{result['version']['id']}/file").content
        data = list(csv.reader(io.StringIO(content.decode(), newline="")))
        assert data[5][1] == data[6][1] == '  New, "name"\r\n001  '


@pytest.mark.parametrize("stage", ["preview", "approve", "execute"])
def test_stale_proposals(client: TestClient, stage: str) -> None:
    saved = upload(client)
    identity = propose(client, saved)
    token = client.post(f"/remediations/{identity}/preview").json()["preview_token"]
    if stage == "execute":
        approve(client, identity)
    assert client.post(f"/datasets/{saved['dataset']['id']}/versions", files={"file": ("new.csv", generate()[0])}).status_code == 200
    response = client.post(f"/remediations/{identity}/{stage}", json={"preview_token": token} if stage == "approve" else None)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "stale_source"
    assert client.get(f"/datasets/{saved['dataset']['id']}/versions").json()["total"] == 2


def test_correction_revalidates_statistics(client: TestClient) -> None:
    saved = upload(client, statistical_fixtures()["outlier.csv"])
    identity = propose(client, saved, records=[{"record_number": 40, "expected_value": "100"}], replacement="59")
    approve(client, identity)
    result = client.post(f"/remediations/{identity}/execute").json()
    assert result["check_run"]["validation_status"] == "passed"
    assert not result["check_run"]["result"]["findings"]
    assert any(item["check_id"] == "STAT_IQR" and item["status"] == "passed"
               for item in result["check_run"]["result"]["analysis_results"])


def test_file_failure_is_audited_without_new_version(client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    saved = upload(client)
    identity = propose(client, saved)
    approve(client, identity)
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError("private values")
    monkeypatch.setattr("src.services.storage.os.link", fail)
    response = client.post(f"/remediations/{identity}/execute")
    assert response.status_code == 503 and "private" not in response.text
    assert client.get(f"/remediations/{identity}").json()["status"] == "failed"
    assert client.get(f"/datasets/{saved['dataset']['id']}/versions").json()["total"] == 1
    assert len(list((settings.storage_dir / "files").iterdir())) == 1
    actions = [event["action"] for event in client.get(f"/datasets/{saved['dataset']['id']}/audit?limit=100").json()["items"]]
    assert actions[-2:] == ["remediation_executing", "remediation_failed"]


@pytest.mark.parametrize("acknowledged", [False, True])
def test_execution_commit_failures(client: TestClient, monkeypatch: pytest.MonkeyPatch, acknowledged: bool) -> None:
    saved = upload(client)
    identity = propose(client, saved)
    approve(client, identity)
    original = Session.commit
    calls = 0
    def fail(session: Session) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            if acknowledged:
                original(session)
            raise OperationalError("commit", {}, Exception("private database error"))
        original(session)
    monkeypatch.setattr(Session, "commit", fail)
    response = client.post(f"/remediations/{identity}/execute")
    assert response.status_code == (200 if acknowledged else 503), response.text
    assert client.get(f"/remediations/{identity}").json()["status"] == ("executed" if acknowledged else "failed")
    assert client.get(f"/datasets/{saved['dataset']['id']}/versions").json()["total"] == (2 if acknowledged else 1)


def test_failed_analysis_does_not_reapply_correction(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services import catalog as module
    saved = upload(client)
    identity = propose(client, saved)
    approve(client, identity)
    original = check_dataset
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("private cell")
    monkeypatch.setattr(module, "check_dataset", fail)
    result = client.post(f"/remediations/{identity}/execute").json()
    assert result["remediation"]["status"] == "executed"
    assert result["check_run"]["processing_status"] == "failed"
    assert result["check_run"]["validation_status"] == "not_available"
    assert client.post(f"/remediations/{identity}/execute").json() == result
    assert not client.get(f"/remediations/{identity}/comparison").json()["checks_comparable"]
    monkeypatch.setattr(module, "check_dataset", original)
    retry = client.post(f"/versions/{result['version']['id']}/check").json()
    assert retry["processing_status"] == "completed"
    assert client.get(f"/datasets/{saved['dataset']['id']}/versions").json()["total"] == 2


@pytest.mark.parametrize("same_proposal", [True, False])
def test_concurrent_execution_creates_one_version(settings: Settings, same_proposal: bool) -> None:
    catalog = Catalog(settings, load_rules(settings.rules_path))
    catalog.initialize()
    service = Remediations(catalog)
    try:
        content = generate()[1]
        saved = catalog.upload(content, parse_dataset(content, "x.csv", settings))
        request = RemediationRequest.model_validate(body(saved.model_dump()))
        first = service.create(request)
        second = first if same_proposal else service.create(request)
        for identity in {first.id, second.id}:
            preview = service.preview(identity)
            service.approve(identity, ApprovalRequest(preview_token=preview.preview_token))
        def execute(identity: str) -> str:
            try:
                return service.execute(identity).version.id
            except InputError as exc:
                return exc.code
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(execute, [first.id, second.id]))
        assert catalog.versions(saved.dataset.id, 100, 0).total == 2
        if same_proposal:
            assert results[0] == results[1]
        else:
            assert results.count("stale_source") == 1
    finally:
        catalog.database.close()


def test_pending_check_resumes_and_hash_tampering_blocks_execution(client: TestClient, settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    saved = upload(client)
    identity = propose(client, saved)
    approve(client, identity)
    original = Catalog.process_check
    def interrupt(self: Catalog, run_id: str) -> Any:
        raise OperationalError("connection", {}, Exception("disconnected"))
    monkeypatch.setattr(Catalog, "process_check", interrupt)
    assert client.post(f"/remediations/{identity}/execute").status_code == 503
    stored = client.get(f"/remediations/{identity}").json()
    assert stored["status"] == "executed"
    assert client.get(f"/check-runs/{stored['check_run_id']}").json()["processing_status"] == "running"
    monkeypatch.setattr(Catalog, "process_check", original)
    assert client.post(f"/remediations/{identity}/execute").json()["check_run"]["processing_status"] == "completed"
    latest = client.get(f"/versions/{stored['result_version_id']}").json()
    identity = propose(client, {"version": latest, "metadata": latest["metadata"]},
                       records=[{"record_number": 8, "expected_value": "100"}], replacement="99")
    approve(client, identity)
    (settings.storage_dir / "files" / latest["file_id"]).write_bytes(b"changed")
    assert client.post(f"/remediations/{identity}/execute").json()["error"]["code"] == "file_integrity_error"
