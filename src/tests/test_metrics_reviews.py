import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from src.main import create_app
from src.models import CheckRun
from src.rules import load_rules
from src.schemas import ReviewRequest
from src.scripts.generate_fixtures import generate
from src.services.catalog import Catalog
from src.services.tabular import ParsedDataset, parse_dataset
from src.services.metrics import quality_metrics
from src.services.validation import check_dataset
from src.settings import Settings
from src.tests.test_persistence import upload


def test_metrics_match_hand_calculated_values(settings: Settings) -> None:
    content = (
        "facility_id,facility_name,county,facility_type,status,inspection_score,inspection_date\n"
        "FAC-000001,A,Alder,Clinic,Active,50,2026-10-07\n"
        "FAC-000001,B,Alder,Clinic,Active,101,2026-10-07\n"
        ",,Alder,Clinic,Active,10,2026-10-07\n"
        "FAC-000004,D,Alder,Clinic,Active,20,2026-10-07\n"
    ).encode()
    result = check_dataset(parse_dataset(content, "x.csv", settings), load_rules(settings.rules_path), settings)
    metrics = result.metrics
    assert (metrics.completeness.numerator, metrics.completeness.denominator) == (18, 20)
    assert metrics.completeness.percentage == 90
    assert (metrics.valid_row_rate.numerator, metrics.valid_row_rate.denominator) == (1, 4)
    assert metrics.valid_row_rate.percentage == 25
    assert (metrics.duplicate_id_rate.numerator, metrics.duplicate_id_rate.denominator) == (2, 3)
    assert metrics.duplicate_id_rate.percentage == pytest.approx(200 / 3)


def test_clean_dirty_fixture_metrics(settings: Settings) -> None:
    rules = load_rules(settings.rules_path)
    clean, dirty, _ = generate()
    clean_metrics = check_dataset(parse_dataset(clean, "clean.csv", settings), rules, settings).metrics
    assert clean_metrics.completeness.percentage == clean_metrics.valid_row_rate.percentage == 100
    assert clean_metrics.duplicate_id_rate.percentage == 0
    dirty_metrics = check_dataset(parse_dataset(dirty, "dirty.csv", settings), rules, settings).metrics
    assert (dirty_metrics.completeness.numerator, dirty_metrics.completeness.denominator) == (743, 750)
    assert (dirty_metrics.valid_row_rate.numerator, dirty_metrics.valid_row_rate.denominator) == (130, 150)
    assert (dirty_metrics.duplicate_id_rate.numerator, dirty_metrics.duplicate_id_rate.denominator) == (3, 148)


def test_unavailable_structure_and_zero_denominators(settings: Settings) -> None:
    rules = load_rules(settings.rules_path)
    missing = check_dataset(parse_dataset(b"facility_id\nFAC-000001\n", "x.csv", settings), rules, settings)
    assert missing.validation_status == "failed"
    assert all(metric["status"] == "not_available" and metric["percentage"] is None for metric in missing.metrics.model_dump().values())
    empty_values = parse_dataset(
        b"facility_id,facility_name,county,facility_type,status,inspection_score,inspection_date\n,,,,,,\n",
        "x.csv", settings,
    )
    metrics = check_dataset(empty_values, rules, settings).metrics
    assert metrics.completeness.percentage == metrics.valid_row_rate.percentage == 0
    assert metrics.duplicate_id_rate.status == "not_available"
    assert metrics.duplicate_id_rate.denominator == 0
    empty_dataset = ParsedDataset(metadata=empty_values.metadata.model_copy(update={"row_count": 0}), records=())
    metrics = quality_metrics(empty_dataset, rules, [])
    assert all(metric["denominator"] == 0 and metric["status"] == "not_available" for metric in metrics.model_dump().values())


def test_reviews_are_append_only_and_survive_restart(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        saved = upload(client)
        run_id, version_id = saved["check_run"]["id"], saved["version"]["id"]
        findings = client.get(f"/check-runs/{run_id}/findings").json()["items"]
        finding = next(f for f in findings if f["rule_id"] == "FAC_ID_UNIQUE")
        finding_id = finding["id"]
        before_run = client.get(f"/check-runs/{run_id}").json()
        before_metrics = client.get(f"/check-runs/{run_id}/metrics").json()
        decisions = [
            {"decision": "needs_correction"},
            {"decision": "accepted_as_is", "reason": " Verified fictional record. "},
            {"decision": "dismissed", "reason": "Reviewed again; retained for audit."},
        ]
        reviews = []
        for decision in decisions:
            response = client.post(f"/findings/{finding_id}/reviews", json=decision)
            assert response.status_code == 201, response.text
            reviews.append(response.json())
        assert reviews[1]["reason"] == "Verified fictional record."
        assert all(r["actor"] == "local_operator" and r["created_at"] for r in reviews)
        assert client.get(f"/check-runs/{run_id}").json() == before_run
        assert client.get(f"/check-runs/{run_id}/metrics").json() == before_metrics
        assert client.get(f"/findings/{finding_id}").json() == finding
        assert client.get(f"/versions/{version_id}/file").content == generate()[1]
    with TestClient(create_app(settings)) as restarted:
        history = restarted.get(f"/findings/{finding_id}/reviews").json()
        assert history["items"] == reviews
        assert history["total"] == 3
        assert restarted.get(f"/findings/{finding_id}/reviews?limit=1&offset=1").json()["items"] == [reviews[1]]
        assert restarted.get(f"/check-runs/{run_id}/metrics").json() == before_metrics
        events = restarted.get(f"/datasets/{saved['dataset']['id']}/audit").json()["items"]
        assert [event["entity_id"] for event in events if event["action"] == "review_added"] == [r["id"] for r in reviews]


@pytest.mark.parametrize("body", [
    {"decision": "accepted_as_is"}, {"decision": "dismissed", "reason": " \t\n "},
    {"decision": "invalid"}, {"decision": "needs_correction", "actor": "other"},
    {"decision": "dismissed", "reason": "x" * 2001},
])
def test_invalid_review_is_rejected_without_history(client: TestClient, body: dict[str, Any]) -> None:
    saved = upload(client)
    finding = client.get(f"/check-runs/{saved['check_run']['id']}/findings").json()["items"][0]
    response = client.post(f"/findings/{finding['id']}/reviews", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert client.get(f"/findings/{finding['id']}/reviews").json()["total"] == 0


def test_missing_finding_review(client: TestClient) -> None:
    assert client.post("/findings/missing/reviews", json={"decision": "needs_correction"}).status_code == 404
    assert client.get("/findings/missing/reviews").status_code == 404


def test_review_and_audit_roll_back_together(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    saved = upload(client)
    finding = client.get(f"/check-runs/{saved['check_run']['id']}/findings").json()["items"][0]
    audit_path = f"/datasets/{saved['dataset']['id']}/audit"
    before = client.get(audit_path).json()
    original_commit = Session.commit

    def fail_commit(session: Session) -> None:
        raise OperationalError("commit", {}, Exception("failure"))

    monkeypatch.setattr(Session, "commit", fail_commit)
    response = client.post(f"/findings/{finding['id']}/reviews", json={"decision": "needs_correction"})
    assert response.status_code == 503
    monkeypatch.setattr(Session, "commit", original_commit)
    assert client.get(f"/findings/{finding['id']}/reviews").json()["total"] == 0
    assert client.get(audit_path).json() == before


def test_concurrent_reviews_do_not_lose_history(settings: Settings) -> None:
    catalog = Catalog(settings, load_rules(settings.rules_path))
    catalog.initialize()
    try:
        content = generate()[1]
        saved = catalog.upload(content, parse_dataset(content, "x.csv", settings))
        finding_id = catalog.findings(saved.check_run.id, 20, 0).items[0].id
        with ThreadPoolExecutor(max_workers=3) as workers:
            reviews = list(workers.map(lambda _: catalog.add_review(finding_id, ReviewRequest(decision="needs_correction")), range(3)))
        assert catalog.reviews(finding_id, 20, 0).total == 3
        assert len({r.id for r in reviews}) == 3
        assert len([a for a in catalog.audit_events(saved.dataset.id, 100, 0).items if a.action == "review_added"]) == 3
    finally:
        catalog.database.close()


def test_old_and_failed_runs_have_unavailable_metrics(settings: Settings) -> None:
    catalog = Catalog(settings, load_rules(settings.rules_path))
    catalog.initialize()
    try:
        content = generate()[0]
        saved = catalog.upload(content, parse_dataset(content, "x.csv", settings))
        with catalog.database.write() as session:
            run = session.scalar(select(CheckRun).where(CheckRun.id == saved.check_run.id))
            assert run and run.result_json
            result = json.loads(run.result_json)
            result.pop("metrics")
            run.result_json = json.dumps(result)
        assert catalog.metrics(saved.check_run.id).completeness.status == "not_available"
        catalog.files.path(saved.version.file_id).unlink()
        failed = catalog.check(saved.version.id)
        assert failed.processing_status == "failed"
        assert catalog.metrics(failed.id).valid_row_rate.status == "not_available"
    finally:
        catalog.database.close()

