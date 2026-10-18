"""Administrative helpers always operate on disposable files and databases here."""
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from src.models import CheckRun
from src.rules import load_rules
from src.scripts import evaluate, generate_fixtures, generate_format_fixtures, generate_statistical_fixtures
from src.scripts import seed_demo
from src.services.catalog import Catalog, require
from src.services.tabular import parse_dataset
from src.settings import Settings
from src.tests.fixture_oracle import validation_fixture


@pytest.fixture
def admin_catalog(settings: Settings) -> Iterator[Catalog]:
    catalog = Catalog(settings, load_rules(settings.rules_path))
    catalog.initialize()
    try:
        yield catalog
    finally:
        catalog.database.close()


def test_fixture_cli_writes_reproducible_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["generate", "--rows", "20", "--output-dir", str(tmp_path)])
    generate_fixtures.main()
    expected = generate_fixtures.generate(20)
    for name, content in zip(["facilities_clean.csv", "facilities_dirty.csv", "facilities_errors.json"], expected, strict=True):
        assert (tmp_path / name).read_bytes() == content


def test_fixture_cli_rejects_incomplete_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["generate", "--rows", "19", "--output-dir", str(tmp_path)])
    with pytest.raises(SystemExit) as caught:
        generate_fixtures.main()
    assert caught.value.code == 2
    assert list(tmp_path.iterdir()) == []


def test_format_generator_outputs_equivalent_records(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    monkeypatch.setattr("sys.argv", ["formats", "--output-dir", str(tmp_path)])
    generate_format_fixtures.main()
    assert len(list(tmp_path.iterdir())) == 8
    for stem in ("facilities_clean", "facilities_dirty"):
        baseline = parse_dataset((tmp_path / (stem + ".csv")).read_bytes(), stem + ".csv", settings)
        for extension in ("tsv", "xlsx", "parquet"):
            path = tmp_path / (stem + "." + extension)
            parsed = parse_dataset(path.read_bytes(), path.name, settings)
            assert parsed.records == baseline.records
            assert parsed.metadata.headers == baseline.metadata.headers


def test_statistical_fixture_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["statistics", "--output-dir", str(tmp_path)])
    generate_statistical_fixtures.main()
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == generate_statistical_fixtures.generate()


def test_evaluation_cli_outputs_perfect_oracle_scores(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr("sys.argv", ["evaluate", "--rows", "20"])
    monkeypatch.setattr(evaluate, "generate", validation_fixture)
    evaluate.main()
    report = json.loads(capsys.readouterr().out)
    assert report["rows"] == 20
    assert report["expected_errors"] == report["detected_errors"] == 24
    assert report["dirty"]["precision"] == report["dirty"]["recall"] == 1


@pytest.fixture
def demo_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    spec = {"id": "b7b3a921-a173-46d8-9d23-c15d2af07af1", "name": "Small demo", "filename": "demo.csv",
        "columns": ["id", "value"], "row_count": 2, "rows": [{"id": "A", "value": "1"}, {"id": "B", "value": "2"}],
        "rules": {"schema_version": 1, "name": "Demo rules", "structural_rule_id": "COLUMNS",
                  "required_columns": [], "identifier_policy": "auto", "rules": []}}
    (tmp_path / "config").mkdir()
    (tmp_path / "config/demo-datasets.json").write_text(json.dumps([spec]), encoding="utf-8")
    monkeypatch.setattr(seed_demo, "PROJECT_ROOT", tmp_path)
    return spec


def test_demo_seeding_is_idempotent_and_preserves_versions(admin_catalog: Catalog, demo_manifest: dict[str, Any]) -> None:
    identity = demo_manifest["id"]
    assert seed_demo.seed_demo(admin_catalog) == [{"id": identity, "created": True, "rows": 2}]
    detail = admin_catalog.detail(identity)
    assert seed_demo.seed_demo(admin_catalog) == [{"id": identity, "created": False}]
    assert admin_catalog.detail(identity) == detail
    assert admin_catalog.versions(identity, 10, 0).total == 1
    assert admin_catalog.datasets(10, 0).total == 1


def test_demo_seeding_retries_failed_analysis(admin_catalog: Catalog, demo_manifest: dict[str, Any]) -> None:
    identity = demo_manifest["id"]
    seed_demo.seed_demo(admin_catalog)
    detail = admin_catalog.detail(identity)
    assert detail.latest_run and detail.selected_version
    with admin_catalog.database.write() as session:
        run = require(session, CheckRun, detail.latest_run.id)
        run.processing_status = "failed"
        run.error_code = "processing_failed"
        run.result_json = None
    assert seed_demo.seed_demo(admin_catalog) == [{"id": identity, "created": False}]
    result = admin_catalog.detail(identity)
    assert result.latest_run and result.latest_run.processing_status == "completed"
    assert admin_catalog.runs(detail.selected_version.id, 10, 0).total == 2
