# Testing

[README](../README.md) · [Rules](RULES.md) · [Frontend testing](../../datagaurd.front-end/docs/TESTING.md)

## Environment and commands

Run from the backend root after installing locked development dependencies:

```powershell
uv sync --locked
uv run pytest
uv run pytest src/tests/unit
uv run mypy src
uv run pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml
```

With an existing Windows environment, substitute `.\.venv\Scripts\python.exe -m pytest` or `-m mypy`. On macOS/Linux, use `.venv/bin/python -m pytest` or `-m mypy`.

Configure test discovery and tooling in [pyproject.toml](../pyproject.toml). Pytest discovers `src/tests`, adds the repository root to the Python path, enforces strict markers, and writes temporary data to `.pytest_tmp`. Review branch coverage for `src` in `output/coverage/` (HTML) or `output/coverage.xml`; coverage excludes test files and enforces no minimum percentage. Run mypy in the configured strict mode with its Pydantic plugin.

## Test coverage map

| Area | Test files |
| --- | --- |
| Foundation, errors, ingestion, formats | `test_foundation.py`, `test_api_errors.py`, `test_ingestion.py`, `test_formats.py` |
| Rules and assignments | `test_rules.py`, `test_generic_rules.py`, `test_rule_assignments.py` |
| Profiles, metrics, statistics, evaluation | `test_profiling.py`, `test_metrics_reviews.py`, `test_statistics.py`, `test_validation.py`, `test_evaluation.py` |
| Persistence and identity | `test_persistence.py`, `test_dataset_identity.py` |
| Review/corrections | `test_cell_review_workflows.py`, `test_remediation.py` |
| Frontend contract/workspace | `test_frontend_contract.py`, `test_workspace_api.py` |
| Administration scripts | `test_admin_scripts.py` |
| Isolated services/models | `unit/test_*.py`: parsing, storage, schemas, identifiers, rule syntax, metrics, reviews, projections |

Run API tests through FastAPI TestClient without starting a separate server. Use the temporary storage and settings from [conftest.py](../src/tests/conftest.py): the fixture clears inherited `DATAGUARD_` values, disables dotenv loading with `_env_file=None`, selects facilities rules, and fixes the reference date. Keep test helpers separate from operational storage.

Run focused suites while developing the corresponding behavior:

```powershell
uv run pytest src/tests/test_workspace_api.py src/tests/test_dataset_identity.py
uv run pytest src/tests/test_remediation.py src/tests/test_cell_review_workflows.py
uv run pytest src/tests/unit/test_rule_syntax.py src/tests/unit/test_frontend_rules.py
```

## Deterministic fixtures

Fixture scripts generate synthetic data. Use explicit output directories to avoid replacing committed fixtures:

```powershell
uv run python -m src.scripts.generate_fixtures --rows 150 --output-dir output/generated-fixtures
uv run python -m src.scripts.generate_format_fixtures --output-dir output/formats
uv run python -m src.scripts.generate_statistical_fixtures --output-dir output/statistical-fixtures
uv run python -m src.scripts.generate_invalid_fixtures
```

| Generator | Output |
| --- | --- |
| `generate_fixtures` | Clean/dirty facilities CSV and expected-error JSON; accepts rows, seed, reference date, output directory |
| `generate_format_fixtures` | Equivalent clean/dirty datasets across CSV, TSV, XLSX, Parquet |
| `generate_statistical_fixtures` | Reproducible baseline/current datasets for schema and drift checks |
| `generate_invalid_fixtures` | Fixed `output/manual-fixtures/` inputs for parsing failures |

Without `--output-dir`, `generate_fixtures` writes into `src/data/`. Regenerate committed fixtures deliberately and review their diff.

## Validation evaluation

```powershell
uv run python -m src.scripts.evaluate --rows 5000
```

Use the evaluation output to compare deterministic `(rule_id, record_number)` detections against the expected manifest. Inspect true/false positives, false negatives, precision, recall, F1, per-rule counts, and reproducibility fields. The evaluator excludes statistical findings from classification metrics and returns null for unavailable ratios. Run API, migration, and persistence tests alongside evaluation.

## Frontend integration

Use isolated storage, seed the demos, and start the API. In the frontend checkout, run `pnpm test:live` to compare live projections/downloads with the in-memory samples through read-only requests. Start with a fresh isolated database because seeding preserves existing edits.

Frontend Playwright workflows use mocked HTTP fixtures and do not verify the running backend. Backend TestClient tests verify service behavior; live parity verifies the shared demo contract. Keep all three layers when changing projections, rule semantics, or identity handling.

## Continuous verification

Configure your backend CI to install locked dependencies and run `uv run mypy src` and `uv run pytest`. Publish coverage artifacts when you generate them. Add a backend workflow separately from the sibling frontend workflow, which tests only the frontend. Investigate failures against the behavior and contracts in these guides.
