from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.main import create_app
from src.rules import load_rules
from src.scripts.generate_fixtures import generate
from src.services.catalog import Catalog
from src.services.tabular import parse_dataset
from src.settings import Settings


def upload(client: TestClient, content: bytes | None = None) -> dict[str, Any]:
    response = client.post("/datasets/upload", files={"file": ("facilities.csv", content or generate()[1], "text/csv")})
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_restart_preserves_versions_runs_findings_and_bytes(settings: Settings) -> None:
    clean, dirty, _ = generate()
    with TestClient(create_app(settings)) as client:
        saved = upload(client, dirty)
        dataset_id, version_id = saved["dataset"]["id"], saved["version"]["id"]
        run_id = saved["check_run"]["id"]
        response = client.post(f"/datasets/{dataset_id}/versions", files={"file": ("clean.csv", clean, "text/csv")})
        assert response.status_code == 200
        second = response.json()
        assert second["version"]["number"] == 2
        assert second["version"]["parent_id"] == version_id
        assert second["check_run"]["validation_status"] == "passed"
        assert saved["check_run"]["validation_status"] == "failed"
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(f"/datasets/{dataset_id}").json() == saved["dataset"]
        assert restarted.get(f"/versions/{version_id}").json() == saved["version"]
        assert restarted.get(f"/check-runs/{run_id}").json() == saved["check_run"]
        assert restarted.get(f"/versions/{version_id}/file").content == dirty
        assert restarted.get(f"/versions/{second['version']['id']}/file").content == clean
        assert restarted.get(f"/datasets/{dataset_id}/versions").json()["total"] == 2
        findings = restarted.get(f"/check-runs/{run_id}/findings").json()
        assert findings["total"] == 12
        duplicate = next(f for f in findings["items"] if f["rule_id"] == "FAC_ID_UNIQUE")
        first = restarted.get(f"/findings/{duplicate['id']}/records?limit=2").json()
        last = restarted.get(f"/findings/{duplicate['id']}/records?limit=2&offset=2").json()
        assert first["total"] == 3
        assert [r["record_number"] for r in first["items"] + last["items"]] == [3, 4, 20]
        assert first["items"][0]["values"]["facility_id"] == "FAC-000003"
        assert restarted.get(f"/findings/{duplicate['id']}").json() == duplicate
        events = restarted.get(f"/datasets/{dataset_id}/audit").json()["items"]
        assert [e["action"] for e in events] == [
            "dataset_created", "version_uploaded", "check_started", "check_completed",
            "version_uploaded", "check_started", "check_completed"]
        assert all(e["actor"] == "local_operator" for e in events)


def test_pagination_and_not_found(client: TestClient) -> None:
    saved = upload(client)
    upload(client)
    first = client.get("/datasets?limit=1").json()
    second = client.get("/datasets?limit=1&offset=1").json()
    assert first["total"] == second["total"] == 2
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert client.get("/datasets?offset=20").json()["items"] == []
    assert client.get("/datasets?limit=101").status_code == 422
    assert client.get("/datasets?offset=-1").status_code == 422
    assert client.get(f"/versions/{saved['version']['id']}/check-runs").json()["total"] == 1
    assert client.get(f"/datasets/{saved['dataset']['id']}/audit?limit=1&offset=1").json()["items"][0]["action"] == "version_uploaded"
    for path in ["datasets", "versions", "check-runs", "findings"]:
        assert client.get(f"/{path}/missing").status_code == 404
    assert client.post("/versions/missing/check").status_code == 404


def test_analysis_failure_retains_file_and_retry_appends_run(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from src.services import catalog as module

    from src.services.validation import check_dataset

    original = check_dataset

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise RuntimeError("private cell contents must not appear in a response")

    monkeypatch.setattr(module, "check_dataset", fail)
    saved = upload(client)
    run = saved["check_run"]
    assert run["processing_status"] == "failed"
    assert run["validation_status"] == "not_available"
    assert run["result"] is None
    assert run["error_code"] == "processing_failed"
    assert "private" not in str(saved)
    version_id = saved["version"]["id"]
    assert client.get(f"/versions/{version_id}/file").content == generate()[1]
    monkeypatch.setattr(module, "check_dataset", original)
    retry = client.post(f"/versions/{version_id}/check").json()
    assert retry["id"] != run["id"]
    assert retry["processing_status"] == "completed"
    assert client.get(f"/check-runs/{run['id']}").json()["processing_status"] == "failed"
    assert client.get(f"/versions/{version_id}/check-runs").json()["total"] == 2


def test_storage_failure_rolls_back_and_reconciles(client: TestClient, monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    def fail(*args: Any, **kwargs: Any) -> Any:
        raise OSError("private filesystem path")

    monkeypatch.setattr("src.services.storage.os.link", fail)
    response = client.post("/datasets/upload", files={"file": ("x.csv", generate()[0], "text/csv")})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "storage_unavailable"
    assert "private" not in response.text
    assert client.get("/datasets").json()["total"] == 0
    assert list((settings.storage_dir / "files").iterdir()) == []


def test_database_commit_failure_does_not_publish_a_version(client: TestClient, monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    original_commit = Session.commit
    calls = 0

    def fail_once(session: Session) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OperationalError("private sql", {}, Exception("private driver error"))
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_once)
    response = client.post("/datasets/upload", files={"file": ("x.csv", generate()[0], "text/csv")})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert "private" not in response.text
    assert client.get("/datasets").json()["total"] == 0
    assert list((settings.storage_dir / "files").iterdir()) == []


def test_result_commit_failure_preserves_failed_attempt(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    original_commit = Session.commit
    calls = 0

    def fail_result(session: Session) -> None:
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OperationalError("commit", {}, Exception("failure"))
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_result)
    saved = upload(client)
    assert saved["check_run"]["processing_status"] == "failed"
    assert client.get(f"/check-runs/{saved['check_run']['id']}/findings").json()["total"] == 0
    assert client.post(f"/versions/{saved['version']['id']}/check").json()["processing_status"] == "completed"


def test_commit_acknowledgement_failure_keeps_committed_file(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    original_commit = Session.commit
    calls = 0

    def fail_after_commit(session: Session) -> None:
        nonlocal calls
        calls += 1
        original_commit(session)
        if calls == 1:
            raise OperationalError("commit", {}, Exception("acknowledgement failure"))

    monkeypatch.setattr(Session, "commit", fail_after_commit)
    response = client.post("/datasets/upload", files={"file": ("x.csv", generate()[0], "text/csv")})
    assert response.status_code == 503
    dataset = client.get("/datasets").json()["items"][0]
    version = client.get(f"/datasets/{dataset['id']}/versions").json()["items"][0]
    assert client.get(f"/versions/{version['id']}/file").content == generate()[0]
    assert client.post(f"/versions/{version['id']}/check").json()["processing_status"] == "completed"


def test_check_creation_failure_returns_saved_version_identity(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    original_commit = Session.commit
    calls = 0

    def fail_start(session: Session) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OperationalError("commit", {}, Exception("failure"))
        original_commit(session)

    monkeypatch.setattr(Session, "commit", fail_start)
    response = client.post("/datasets/upload", files={"file": ("x.csv", generate()[0], "text/csv")})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "analysis_unavailable"
    version_id = response.json()["error"]["details"]["version_id"]
    assert client.get(f"/versions/{version_id}/file").content == generate()[0]
    assert client.post(f"/versions/{version_id}/check").json()["processing_status"] == "completed"


def test_startup_reconciles_orphans_but_keeps_committed_files(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        saved = upload(client)
    directory = settings.storage_dir / "files"
    (directory / ("a" * 32 + ".pending")).write_bytes(b"partial")
    (directory / ("b" * 32 + ".csv")).write_bytes(b"orphan")
    (directory / "unmanaged.txt").write_bytes(b"keep")
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/versions/{saved['version']['id']}/file").content == generate()[1]
    assert sorted(p.name for p in directory.iterdir()) == sorted([saved["version"]["file_id"], "unmanaged.txt"])


def test_changed_or_missing_file_is_not_reported_as_passing(client: TestClient, settings: Settings) -> None:
    saved = upload(client)
    path = settings.storage_dir / "files" / saved["version"]["file_id"]
    path.write_bytes(b"changed")
    response = client.post(f"/versions/{saved['version']['id']}/check").json()
    assert response["processing_status"] == "failed"
    assert response["error_code"] == "file_integrity_error"
    assert client.get(f"/versions/{saved['version']['id']}/file").status_code == 503
    path.unlink()
    assert client.post(f"/versions/{saved['version']['id']}/check").json()["validation_status"] == "not_available"


def test_concurrent_versions_use_unique_numbers_and_parent_chain(settings: Settings) -> None:
    catalog = Catalog(settings, load_rules(settings.rules_path))
    catalog.initialize()
    content = generate()[0]
    parsed = parse_dataset(content, "x.csv", settings)
    first = catalog.upload(content, parsed)
    try:
        with ThreadPoolExecutor(max_workers=3) as workers:
            results = list(workers.map(lambda _: catalog.upload(content, parsed, first.dataset.id), range(3)))
        versions = catalog.versions(first.dataset.id, 100, 0).items
        assert [v.number for v in versions] == [1, 2, 3, 4]
        assert [v.parent_id for v in versions] == [None] + [v.id for v in versions[:-1]]
        assert len({v.file_id for v in versions}) == 4
        assert all(result.check_run.processing_status == "completed" for result in results)
        assert all(catalog.version_content(v.id)[0] == content for v in versions)
    finally:
        catalog.database.close()


def test_database_schema_matches_migration(settings: Settings) -> None:
    from alembic.autogenerate import compare_metadata
    from alembic.migration import MigrationContext
    from src.models import Base

    catalog = Catalog(settings, load_rules(settings.rules_path))
    catalog.initialize()
    try:
        with catalog.database.engine.connect() as connection:
            assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    finally:
        catalog.database.close()

