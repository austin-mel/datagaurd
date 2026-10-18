from datetime import datetime, timezone

import pytest

from src.rules import RuleSet
from src.schemas import DatasetDetail, DatasetView, QualityMetrics, RuleSetView, RunView, VersionView
from src.services.frontend_repository import dataset_to_frontend, download_filename
from src.services.metrics import percentage
from src.services.tabular import parse_dataset
from src.services.validation import check_dataset
from src.settings import Settings

pytestmark = pytest.mark.unit


@pytest.fixture
def detail(settings: Settings, simple_rules: RuleSet) -> DatasetDetail:
    now = datetime(2026, 10, 7, tzinfo=timezone.utc)
    parsed = parse_dataset(b"id,value\nA,1\nB,2.5\n", "prices.csv", settings)
    result = check_dataset(parsed, simple_rules, settings)
    assignment = RuleSetView(id="rules", name=simple_rules.name, revision=1, parent_id=None, configuration=simple_rules,
        configuration_sha256=result.configuration_sha256, actor="tester", created_at=now, is_default=False)
    version = VersionView(id="version", dataset_id="dataset", number=2, parent_id="original", file_id="a" * 32 + ".csv",
                          metadata=parsed.metadata, created_at=now)
    run = RunView(id="run", version_id=version.id, processing_status="completed", validation_status="passed",
        configuration=simple_rules, reference_date=result.reference_date, implementation_version=result.implementation_version,
        settings_snapshot=result.settings_snapshot, baseline_id=None, actor="tester", created_at=now,
        completed_at=now, error_code=None, result=result, rule_set_id=assignment.id)
    return DatasetDetail(dataset=DatasetView(id="dataset", name="Prices", created_at=now, rule_set_id=assignment.id),
        selected_version=version, latest_version_id=version.id, latest_run=run, assigned_rules=assignment,
        rules_changed_since_run=False, uploaded_at=now, uploaded_by="tester", recent_events=[], cell_review=[])


@pytest.mark.parametrize(("original", "expected"), [
    ("prices.csv", "prices_v2.csv"), ("../../orders.csv", "orders_v2.csv"),
    (r"C:\private\orders.xlsx", "orders_v2.csv"), ('a"\r\nb.csv', "a___b_v2.csv"),
    ("café.csv", "caf__v2.csv"), ("...", "dataset_v2.csv"),
])
def test_download_filename_is_safe_and_versioned(original: str, expected: str) -> None:
    assert download_filename(original, 2, "csv") == expected


def test_completed_projection_and_mixed_numeric_summary(detail: DatasetDetail) -> None:
    document = dataset_to_frontend(detail)
    assert document["status"] == "healthy" and document["quality"] == 100
    assert document["isCurrentVersion"] and document["version"] == "v2"
    assert document["downloadFilename"] == "Prices_v2.csv"
    assert document["uploadedBy"] == "tester"
    assert document["columnProfiles"] == [
        {"name": "id", "observedTypes": ["text"], "missingCount": 0, "warningCount": 0,
         "uniqueCount": 2, "summary": {"kind": "top-values", "values": [{"value": "A", "count": 1}, {"value": "B", "count": 1}]}},
        {"name": "value", "observedTypes": ["integer", "number"], "missingCount": 0, "warningCount": 0,
         "uniqueCount": 2, "summary": {"kind": "number-range", "minimum": 1., "maximum": 2.5}},
    ]


@pytest.mark.parametrize("status", ["running", "failed"])
def test_incomplete_runs_do_not_display_old_scores(detail: DatasetDetail, status: str) -> None:
    assert detail.latest_run is not None
    detail.latest_run = detail.latest_run.model_copy(update={"processing_status": status, "error_code": "processing_failed" if status == "failed" else None})
    document = dataset_to_frontend(detail)
    assert document["status"] == status
    assert document["quality"] is None
    assert document["columnProfiles"] is None and document["validation"] is None
    if status == "failed":
        assert document["processingError"] == "processing_failed"


def test_dataset_without_upload_or_run_has_explicit_empty_state(detail: DatasetDetail) -> None:
    detail.selected_version = detail.latest_run = None
    detail.uploaded_at = detail.uploaded_by = None
    document = dataset_to_frontend(detail)
    assert document["status"] == "unvalidated" and document["rowCount"] == 0
    assert document["columns"] == [] and document["version"] == "Not available"
    assert not document["isCurrentVersion"]
    assert "filename" not in document and "uploadedAt" not in document


def test_overall_quality_averages_only_available_dimensions(detail: DatasetDetail) -> None:
    assert detail.latest_run and detail.latest_run.result
    detail.latest_run.result.metrics = QualityMetrics(completeness=percentage(1, 2), valid_row_rate=percentage(3, 4))
    assert dataset_to_frontend(detail)["quality"] == 62.5


def test_edited_data_note_takes_priority_over_ignore_note(detail: DatasetDetail) -> None:
    detail.data_changed_since_run = True
    detail.ignored_cell_count = 2
    assert dataset_to_frontend(detail)["qualityNote"] == "Data changed. Run validation to calculate profiles, issues, and quality scores."


def test_date_summary_uses_iso_bounds(detail: DatasetDetail, settings: Settings, simple_rules: RuleSet) -> None:
    assert detail.latest_run
    parsed = parse_dataset(b"id,value\nA,2026-01-01\nB,2026-10-07\n", "data.csv", settings)
    detail.latest_run.result = check_dataset(parsed, simple_rules, settings)
    profiles = dataset_to_frontend(detail)["columnProfiles"]
    assert isinstance(profiles, list) and isinstance(profiles[1], dict)
    assert profiles[1]["summary"] == {"kind": "date-range", "minimum": "2026-01-01", "maximum": "2026-10-07"}
