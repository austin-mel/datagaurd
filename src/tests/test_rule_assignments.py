import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import yaml
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from src.main import create_app
from src.rules import RuleSet, load_rules
from src.services.catalog import Catalog
from src.services.tabular import parse_dataset
from src.settings import PROJECT_ROOT, Settings


def configuration(name: str = "Orders", allowed: str = "open") -> dict[str, Any]:
    return {"schema_version": 1, "name": name, "structural_rule_id": "COLUMNS",
            "required_columns": ["order_id", "status"], "identifier_column": "order_id",
            "rules": [
                {"id": "ID_REQUIRED", "kind": "required", "column": "order_id", "explanation": "An ID is required."},
                {"id": "ID_UNIQUE", "kind": "unique", "column": "order_id", "explanation": "IDs are unique."},
                {"id": "STATUS_ALLOWED", "kind": "allowed_values", "column": "status", "values": [allowed],
                 "explanation": "Use the dataset's allowed status."}]}


def register(client: TestClient, **kwargs: Any) -> dict[str, Any]:
    response = client.post("/rule-sets", json=configuration(**kwargs))
    assert response.status_code == 201, response.text
    return dict(response.json())


def upload(client: TestClient, rule_id: str) -> dict[str, Any]:
    response = client.post("/datasets/upload", data={"rule_set_id": rule_id},
                           files={"file": ("orders.csv", b"order_id,status\n001,open\n001,closed\n")})
    assert response.status_code == 200, response.text
    return dict(response.json())


def test_individual_assignments_revisions_and_history(client: TestClient) -> None:
    first_rules = register(client)
    other_rules = register(client, name="Other", allowed="closed")
    first, other = upload(client, first_rules["id"]), upload(client, other_rules["id"])
    for saved, number in ((first, 2), (other, 1)):
        run = saved["check_run"]
        finding = next(item for item in run["result"]["findings"] if item["rule_id"] == "STATUS_ALLOWED")
        assert finding["affected_record_numbers"] == [number]
        assert run["result"]["metrics"]["duplicate_id_rate"]["percentage"] == 100
        assert client.get(f"/datasets/{saved['dataset']['id']}/rule-set").json()["id"] == saved["dataset"]["rule_set_id"]
    revision = register(client, allowed="closed")
    assert (revision["revision"], revision["parent_id"]) == (2, first_rules["id"])
    dataset_id = first["dataset"]["id"]
    assert client.get(f"/datasets/{dataset_id}").json()["rule_set_id"] == first_rules["id"]
    assert client.get(f"/rule-sets/{first_rules['id']}").json() == first_rules
    response = client.put(f"/datasets/{dataset_id}/rule-set", json={"rule_set_id": revision["id"]})
    assert response.status_code == 200
    client.put(f"/datasets/{dataset_id}/rule-set", json={"rule_set_id": revision["id"]})
    assignments = [event for event in client.get(f"/datasets/{dataset_id}/audit").json()["items"]
                   if event["action"] == "rule_set_assigned"]
    assert len(assignments) == 1 and assignments[0]["entity_id"] == revision["id"]
    recheck = client.post(f"/versions/{first['version']['id']}/check").json()
    assert recheck["rule_set_id"] == revision["id"]
    assert client.get(f"/check-runs/{first['check_run']['id']}").json() == first["check_run"]
    assert client.get(f"/datasets/{other['dataset']['id']}").json()["rule_set_id"] == other_rules["id"]
    next_version = client.post(f"/datasets/{dataset_id}/versions",
                               files={"file": ("x.tsv", b"order_id\tstatus\n002\tclosed\n")}).json()
    assert next_version["check_run"]["rule_set_id"] == revision["id"]
    assert next_version["check_run"]["validation_status"] == "passed"
    listed = client.get("/rule-sets?limit=1&offset=1").json()
    assert listed["total"] == 4 and len(listed["items"]) == 1


def test_invalid_rules_and_assignment_are_atomic(client: TestClient, settings: Settings) -> None:
    config = configuration()
    config["identifier_column"] = "unknown"
    assert client.post("/rule-sets", json=config).status_code == 422
    config = configuration()
    config["rules"][0]["kind"] = "unknown"
    assert client.post("/rule-sets", json=config).status_code == 422
    config = configuration()
    config["statistics"] = {"iqr_multiplier": -1}
    assert client.post("/rule-sets", json=config).status_code == 422
    for endpoint in ("upload", "profile", "check"):
        response = client.post("/datasets/" + endpoint, data={"rule_set_id": "missing"},
                               files={"file": ("x.csv", b"id\n1\n")})
        assert response.status_code == 404
    assert client.get("/datasets").json()["total"] == 0
    assert not list((settings.storage_dir / "files").iterdir())
    saved = upload(client, register(client)["id"])
    response = client.put(f"/datasets/{saved['dataset']['id']}/rule-set", json={"rule_set_id": "missing"})
    assert response.status_code == 404
    assert client.get(f"/datasets/{saved['dataset']['id']}").json() == saved["dataset"]
    assert client.put("/datasets/missing/rule-set", json={"rule_set_id": saved["dataset"]["rule_set_id"]}).status_code == 404


def test_statistics_are_dataset_specific(client: TestClient) -> None:
    content = b"order_id,status\n" + b"001,open\n" * 20
    newer = b"order_id,status\n" + b"001,open\n" * 30
    for threshold, status in ((20, "review_required"), (100, "passed")):
        config = configuration(name=f"Threshold {threshold}")
        config["statistics"] = {"row_count_change_percentage": threshold}
        rule_id = client.post("/rule-sets", json=config).json()["id"]
        saved = client.post("/datasets/upload", files={"file": ("x.csv", content)}, data={"rule_set_id": rule_id}).json()
        response = client.post(f"/datasets/{saved['dataset']['id']}/versions", files={"file": ("x.csv", newer)})
        assert response.status_code == 200, response.text
        result = response.json()["check_run"]["result"]
        assert result["settings_snapshot"]["row_count_change_percentage"] == threshold
        assert next(item for item in result["analysis_results"] if item["check_id"] == "STAT_ROW_COUNT")["status"] == status


def test_restart_pins_existing_datasets_and_concurrent_revisions(settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(configuration()), encoding="utf-8")
    configured = settings.model_copy(update={"rules_path": path})
    with TestClient(create_app(configured)) as client:
        original_default = next(item for item in client.get("/rule-sets").json()["items"] if item["is_default"])
        saved = upload(client, original_default["id"])
    path.write_text(yaml.safe_dump(configuration(allowed="closed")), encoding="utf-8")
    with TestClient(create_app(configured)) as client:
        current_default = next(item for item in client.get("/rule-sets").json()["items"] if item["is_default"])
        assert current_default["id"] != original_default["id"]
        recheck = client.post(f"/versions/{saved['version']['id']}/check").json()
        assert recheck["rule_set_id"] == original_default["id"]
        assert recheck["configuration"] == original_default["configuration"]
    catalog = Catalog(configured, load_rules(path))
    catalog.initialize()
    try:
        with ThreadPoolExecutor(max_workers=3) as workers:
            revisions = list(workers.map(lambda _: catalog.create_rule_set(RuleSet.model_validate(configuration())), range(3)))
        assert sorted(row.revision for row in revisions) == [3, 4, 5]
    finally:
        catalog.database.close()


def test_legacy_database_upgrade_preserves_dataset_rules(settings: Settings) -> None:
    catalog = Catalog(settings, load_rules(settings.rules_path))
    settings.storage_dir.mkdir(parents=True)
    content = b"order_id,status\n001,open\n"
    metadata = parse_dataset(content, "orders.csv", settings).metadata.model_dump()
    for field in ("format", "sheet_name"):
        metadata.pop(field)
    file_id = "a" * 32 + ".csv"
    catalog.files.publish(file_id, content)
    with catalog.database.engine.connect() as connection:
        config = Config(str(PROJECT_ROOT / "alembic.ini"))
        config.attributes["connection"] = connection
        command.upgrade(config, "0003")
        connection.exec_driver_sql("INSERT INTO datasets VALUES (?, ?, ?)", ("dataset", "Orders", "2026-10-07T00:00:00+00:00"))
        connection.exec_driver_sql("INSERT INTO dataset_versions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("version", "dataset", 1, None, file_id, hashlib.sha256(content).hexdigest(), "orders.csv",
             json.dumps(metadata), "2026-10-07T00:00:00+00:00"))
        connection.exec_driver_sql("INSERT INTO check_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("run", "version", "failed", json.dumps(configuration()), '{"row_count_change_percentage": 50}',
             "2026-10-07", "facilities-validation/1.1.0", None, None, "processing_failed", "operator",
             "2026-10-07T00:00:00+00:00", "2026-10-07T00:00:00+00:00"))
        connection.commit()
    catalog.initialize()
    try:
        assigned = catalog.rule_set(catalog.dataset("dataset").rule_set_id)
        assert assigned.name == "Orders"
        assert assigned.configuration.statistics is not None
        assert assigned.configuration.statistics.row_count_change_percentage == 50
        assert catalog.version_content("version")[0] == content
        assert catalog.check("version").validation_status == "passed"
        assert catalog.run("run").implementation_version == "facilities-validation/1.1.0"
    finally:
        catalog.database.close()
