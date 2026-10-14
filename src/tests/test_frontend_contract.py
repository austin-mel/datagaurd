from collections.abc import Iterator
from datetime import date
from typing import Any

import pytest
from pydantic import ValidationError

from src.errors import InputError
from src.models import CheckRun, DatasetVersion
from src.rules import RuleSet
from src.services.catalog import Catalog, require
from src.services.tabular import parse_dataset
from src.services.validation import check_dataset
from src.settings import Settings


def config(rules: list[dict[str, Any]], columns: list[str] | None = None) -> RuleSet:
    return RuleSet.model_validate({
        "schema_version": 1, "name": "UI rules", "structural_rule_id": "COLUMNS",
        "required_columns": columns or ["id", "email", "amount", "day"],
        "rules": [{"explanation": "Check value.", **rule} for rule in rules],
    })


@pytest.fixture
def catalog(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Iterator[Catalog]:
    service = Catalog(settings, config([{"id": "UNIQUE_ID", "kind": "unique", "column": "id"}], ["id"]))
    service.initialize()
    # Isolate these service-contract tests from hard-link publication (covered by persistence tests).
    def publish(file_id: str, content: bytes) -> None:
        service.files.directory.mkdir(parents=True, exist_ok=True)
        with service.files.path(file_id).open("xb") as stream:
            stream.write(content)
    monkeypatch.setattr(service.files, "publish", publish)
    try:
        yield service
    finally:
        service.database.close()


def test_row_scores_count_each_row_once_and_all_unique_tags(settings: Settings) -> None:
    rules = config([
        {"id": "ID_UNIQUE", "kind": "unique", "column": "id"},
        {"id": "EMAIL_UNIQUE", "kind": "unique", "column": "email"},
        {"id": "AMOUNT_NUMBER", "kind": "numeric", "column": "amount"},
        {"id": "AMOUNT_MIN", "kind": "min", "column": "amount", "minimum": 0, "prerequisite": "AMOUNT_NUMBER"},
        {"id": "AMOUNT_WARNING", "kind": "max", "column": "amount", "maximum": 5,
         "prerequisite": "AMOUNT_NUMBER", "severity": "warning"},
    ])
    parsed = parse_dataset(b"id,email,amount,day\n1,a,1,\n1,b,-1,2026-10-07\n3,b,10,2026-10-07\n4,,1,2026-10-07\n5,e,1,2026-10-07\n", "x.csv", settings)
    metrics = check_dataset(parsed, rules, settings).metrics
    assert (metrics.completeness.numerator, metrics.completeness.denominator) == (3, 5)
    assert (metrics.valid_row_rate.numerator, metrics.valid_row_rate.denominator) == (2, 5)
    assert (metrics.uniqueness.numerator, metrics.uniqueness.denominator) == (1, 5)


@pytest.mark.parametrize(("kind", "extra", "bad_rows"), [
    ("min", {"minimum": 5}, [1]),
    ("max", {"maximum": 5}, [3]),
    ("range", {"minimum": 4, "maximum": 5}, [3]),
])
def test_numeric_boundaries_and_failed_prerequisites(settings: Settings, kind: str,
                                                    extra: dict[str, int], bad_rows: list[int]) -> None:
    rules = config([
        {"id": "NUMBER", "kind": "numeric", "column": "amount"},
        {"id": "BOUND", "kind": kind, "column": "amount", "prerequisite": "NUMBER", **extra},
    ], ["amount"])
    result = check_dataset(parse_dataset(b"amount\n4\n5\n6\nbad\n \n", "x.csv", settings), rules, settings)
    findings = {item.rule_id: item.affected_record_numbers for item in result.findings}
    assert findings == {"NUMBER": [4], "BOUND": bad_rows}
    assert result.rule_results[-1].evaluated_count == 3


@pytest.mark.parametrize(("kind", "affected"), [
    ("not_future", [3]), ("before_today", [2, 3]), ("after_today", [1, 2]), ("on_or_after_today", [1]),
])
def test_relative_dates_include_exact_today_boundary(settings: Settings, kind: str, affected: list[int]) -> None:
    rules = config([
        {"id": "DATE_PARSE", "kind": "date", "column": "day", "formats": ["%Y-%m-%d"]},
        {"id": "DATE_BOUND", "kind": kind, "column": "day", "prerequisite": "DATE_PARSE"},
    ], ["day"])
    parsed = parse_dataset(b"day\n2026-10-06\n2026-10-07\n2026-10-08\nbad\n \n", "x.csv", settings)
    result = check_dataset(parsed, rules, settings.model_copy(update={"reference_date": date(2026, 10, 7)}))
    assert {item.rule_id: item.affected_record_numbers for item in result.findings} == {"DATE_PARSE": [4], "DATE_BOUND": affected}


def test_disabled_rules_and_dependencies(settings: Settings) -> None:
    rules = config([{"id": "ID_UNIQUE", "kind": "unique", "column": "id", "enabled": False}], ["id"])
    result = check_dataset(parse_dataset(b"id\n1\n1\n", "x.csv", settings), rules, settings)
    assert not result.findings
    assert result.metrics.uniqueness.status == "not_available"
    with pytest.raises(ValidationError, match="enabled prerequisite"):
        config([
            {"id": "PARSE", "kind": "numeric", "column": "amount", "enabled": False},
            {"id": "MINIMUM", "kind": "min", "column": "amount", "minimum": 0, "prerequisite": "PARSE"},
        ])


def test_detail_revalidation_preserves_source_history_and_assignment(catalog: Catalog) -> None:
    content = b"id\n1\n1\n"
    original = catalog.upload(content, parse_dataset(content, "original.csv", catalog.settings))
    original_detail = catalog.detail(original.dataset.id)
    new_rules = catalog.create_rule_set(config([{"id": "ID_REQUIRED", "kind": "required", "column": "id"}], ["id"]))
    catalog.assign_rules(original.dataset.id, new_rules.id)
    assert catalog.detail(original.dataset.id).rules_changed_since_run
    detail = catalog.revalidate(original.dataset.id, original.version.id)
    assert detail.selected_version and detail.latest_run and detail.latest_run.result
    assert detail.selected_version.number == 2
    assert detail.selected_version.parent_id == original.version.id
    assert detail.latest_run.rule_set_id == new_rules.id
    assert detail.latest_run.validation_status == "passed"
    assert detail.latest_run.result.profile.row_count == 2
    assert detail.latest_run.result.checked_at
    assert not detail.rules_changed_since_run
    assert detail.uploaded_by == catalog.settings.actor
    assert detail.uploaded_at == original_detail.uploaded_at
    assert catalog.version_content(detail.selected_version.id)[0] == content
    assert catalog.run(original.check_run.id) == original.check_run
    with pytest.raises(InputError, match="newer version"):
        catalog.revalidate(original.dataset.id, original.version.id)
    assert catalog.detail(original.dataset.id, original.version.id).latest_run == original.check_run


def test_detail_selects_latest_beyond_first_page_and_tied_timestamps(catalog: Catalog, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.services.catalog.now", lambda: "2026-10-07T00:00:00+00:00")
    content = b"id\n1\n"
    saved = catalog.upload(content, parse_dataset(content, "x.csv", catalog.settings))
    for _ in range(22):
        newest = catalog.revalidate(saved.dataset.id, catalog.detail(saved.dataset.id).latest_version_id or "")
    assert newest.selected_version and newest.selected_version.number == 23
    version_id = newest.selected_version.id
    for _ in range(22):
        with catalog.database.write() as session:
            last_run = catalog.start_check(session, require(session, DatasetVersion, version_id))
    detail = catalog.detail(saved.dataset.id)
    assert detail.latest_run and detail.latest_run.id == last_run.id
    assert detail.latest_run.processing_status == "running" and detail.latest_run.result is None
    with catalog.database.write() as session:
        row = require(session, CheckRun, last_run.id)
        row.processing_status = "failed"
        row.error_code = "processing_failed"
    detail = catalog.summaries(1, 0).items[0]
    assert detail.latest_run and detail.latest_run.id == last_run.id
    assert detail.latest_run.validation_status == "not_available"
    assert detail.latest_run.result is None
    assert len(detail.recent_events) == 20


def test_failed_revalidation_and_cross_dataset_selection(catalog: Catalog, monkeypatch: pytest.MonkeyPatch) -> None:
    content = b"id\n1\n"
    saved = catalog.upload(content, parse_dataset(content, "x.csv", catalog.settings))
    other = catalog.upload(content, parse_dataset(content, "y.csv", catalog.settings))
    with pytest.raises(InputError, match="does not belong"):
        catalog.detail(saved.dataset.id, other.version.id)
    def fail(*args: Any, **kwargs: Any) -> None:
        raise ValueError("Invalid parser input")
    monkeypatch.setattr(catalog, "parsed_version", fail)
    detail = catalog.revalidate(saved.dataset.id, saved.version.id)
    assert detail.selected_version and detail.selected_version.number == 2
    assert detail.latest_run and detail.latest_run.processing_status == "failed"
    assert detail.latest_run.result is None
    assert catalog.version_content(saved.version.id)[0] == content
