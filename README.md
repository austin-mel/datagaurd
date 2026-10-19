# DataGuard API and Backend Setup

## Table of Contents

- [Data Quality API](#data-quality-api)
- [Technology Stack](#technology-stack)
- [Requirements](#requirements)
- [Local Setup](#local-setup)
  - [Check Your Development Tools](#check-your-development-tools)
  - [Start the Backend](#start-the-backend)
  - [Start the Frontend](#start-the-frontend)
  - [Verify the Setup](#verify-the-setup)
- [Repository Layout](#repository-layout)
- [Explore the Demo Datasets](#explore-the-demo-datasets)
- [Development Commands](#development-commands)
- [Data and Privacy](#data-and-privacy)
- [Documentation](#documentation)
  - [Configure and Operate the API](#configure-and-operate-the-api)
  - [Work with Your Data](#work-with-your-data)
  - [Integrate and Develop](#integrate-and-develop)

## Data Quality API

Use DataGuard's API to assess CSV, TSV, Excel, and Parquet datasets. Profile columns, define dataset-specific rules, calculate row-based quality metrics, identify statistical changes, and record review decisions and corrections.

Preserve your original files and trace each version, rule revision, check attempt, finding, and audit event. Connect the Vue frontend through the versioned workspace API, or use the lower-level endpoints to build ingestion, analysis, history, and approved-remediation workflows.

## Technology Stack

[![Python](https://img.shields.io/badge/Python_3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/tutorial/)
[![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/latest/install/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/download.html)
[![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org/download.html)
[![Alembic](https://img.shields.io/badge/Alembic-6BA81E?style=for-the-badge&logo=alembic&logoColor=white)](https://alembic.sqlalchemy.org/en/latest/front.html)
[![pandas](https://img.shields.io/badge/pandas-150458?style=for-the-badge&logo=pandas&logoColor=white)](https://pandas.pydata.org/docs/getting_started/install.html)
[![PyArrow](https://img.shields.io/badge/PyArrow-E34F26?style=for-the-badge&logo=apachearrow&logoColor=white)](https://arrow.apache.org/docs/python/install.html)
[![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)](https://docs.pytest.org/en/stable/getting-started.html)
[![uv](https://img.shields.io/badge/uv-DE5FE9?style=for-the-badge&logo=uv&logoColor=white)](https://docs.astral.sh/uv/getting-started/installation/)

Find dependency ranges in [pyproject.toml](pyproject.toml) and exact resolved versions in [uv.lock](uv.lock).

## Requirements

Install the required tools before setting up the application.

| Tool                                                              | Purpose                                                                                             |
| ----------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| [Python](https://www.python.org/downloads/)                       |`3.12` or newer. Run the API, tests, and administration scripts                                      |
| [uv](https://docs.astral.sh/uv/getting-started/installation/)     | Install backend dependencies from the lockfile `uv.lock`                                            |
| [Git](https://git-scm.com/downloads)                              | Clone the project branches.                                                                         |
| [Visual Studio Code](https://code.visualstudio.com/)   | Edit source and environment files, or use your preferred editor.                                    |

Use the embedded SQLite database without installing a separate database server.

## Local Setup

### Check Your Development Tools

Open the backend checkout and verify the tools:

```powershell
python --version
uv --version
```

If you have not installed uv, run `python -m pip install uv`, then reopen your terminal if necessary to refresh PATH.

### Start the Backend

1. Install the locked dependencies, including the development group:

   ```powershell
   uv sync --locked
   ```

2. Create the local environment file if it does not already exist:

   ```powershell
   Copy-Item environment/.example.back-end.env environment/.back-end.env
   ```

3. Set the storage location and permitted frontend origins in `environment/.back-end.env`:

   ```dotenv
   DATAGUARD_STORAGE_DIR=storage
   DATAGUARD_CORS_ORIGINS=["http://127.0.0.1:5173","http://localhost:5173"]
   DATAGUARD_ACTOR=local_operator
   ```

4. Load the sample datasets if you want a populated development workspace:

   ```powershell
   uv run python -m src.scripts.seed_demo
   ```

5. Start the API:

   ```powershell
   uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
   ```

When you start the backend, it initializes SQLite, applies migrations, registers default rules, and reconciles managed files. Use a new, empty storage directory for the current schema baseline if you previously ran an earlier development version; see [Operations](docs/OPERATIONS.md#migrations). Run the seed command to add examples without replacing existing demo datasets. Keep the server terminal running; use Ctrl+C to stop it.

Run these commands from the backend root. Relative storage paths resolve from your process working directory. Consult [Configuration](docs/CONFIGURATION.md) for every setting.

For an existing Windows virtual environment, use `.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload`. On macOS/Linux, the equivalent interpreter is `.venv/bin/python`; use `cp` instead of `Copy-Item` when copying configuration.

### Start the Frontend

In a second terminal:

```powershell
Set-Location ../datagaurd.front-end
pnpm install --frozen-lockfile
pnpm dev
```

Open [DataGuard](http://127.0.0.1:5173/datagaurd/) and confirm **Connected to backend · Live data**. The frontend uses `/datagaurd/` as its application base path. The default Vite proxy sends `/api` to port 8000; workspace API requests still use `/api/v1`. For overrides, use the frontend's `environment/front-end.env`; see the [frontend README](../datagaurd.front-end/README.md).

### Verify the Setup

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/upload-policy
uv run pytest
uv run mypy src
```

Confirm that the health endpoint returns `{ "status": "ok" }`. Browse the API using [Swagger UI](http://127.0.0.1:8000/docs), [ReDoc](http://127.0.0.1:8000/redoc), or [OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

## Repository Layout

```text
datagaurd/
  datagaurd.front-end/   # Vue application and browser tests
  datagaurd.back-end/    # API, migrations, source files, and metadata
```

Install dependencies and configure environment files independently in each project. Run backend commands from `datagaurd.back-end/`; the parent directory has no shared package or environment file.

| Backend path | Use it for |
| --- | --- |
| `src/main.py`, `src/*routes.py` | Application startup and HTTP routes |
| `src/services/` | Ingestion, analysis, persistence, reviews, and workspace projections |
| `src/models.py`, `src/schemas.py`, `src/rules.py` | Database records, API models, and rule definitions |
| `src/migrations/` | Alembic schema migrations |
| `src/scripts/`, `src/data/` | Administration commands and synthetic fixtures |
| `src/tests/` | API, integration, and unit tests |
| `config/` | Default rules and the shared demo manifest |
| `environment/` | Example and local backend configuration |
| `storage/` | Default SQLite database and immutable source files |
| `docs/` | API references and workflow guides |

## Explore the Demo Datasets

1. Seed the examples and start the API and frontend.
2. Open **County facilities** and inspect its profile, validation findings, and quality scores.
3. Create a custom ruleset and run validation to apply it.
4. Correct a flagged cell, save the new version, and run validation again.
5. Download a version and inspect the dataset history.
6. Upload a synthetic dataset through the frontend or [ingestion API](docs/INGESTION.md).
7. Use the [review and correction endpoints](docs/REVIEW_DATASETS.md) to annotate findings or preview, approve, and execute an exact replacement.

| Dataset | Rows | Columns | Stable ID |
| --- | ---: | ---: | --- |
| County facilities | 20 | 6 | `3be295a2-aad7-4724-9853-44729e762066` |
| Office inventory | 12 | 5 | `8e6483be-d006-4ab9-84c8-e86eac26b997` |
| Customer master | 248,512 | 4 | `9e716851-5f95-4433-b771-d336b0d00d20` |

Use the examples to explore intentional errors and statistical anomalies. You can repeat the seed command without replacing existing source versions or edits. Treat each ordinary upload as a new dataset: the backend assigns a fresh UUID even when the name and content match an earlier upload.

## Development Commands

| Task | Command |
| --- | --- |
| Install locked dependencies | `uv sync --locked` |
| Development server | `uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload` |
| Full test suite | `uv run pytest` |
| Unit tests | `uv run pytest src/tests/unit` |
| Type-check | `uv run mypy src` |
| Coverage | `uv run pytest --cov=src --cov-report=term-missing --cov-report=html --cov-report=xml` |
| Apply schema migrations | `uv run alembic upgrade head` |
| Seed examples | `uv run python -m src.scripts.seed_demo` |
| Evaluate validation | `uv run python -m src.scripts.evaluate --rows 5000` |

Follow [Operations](docs/OPERATIONS.md) for administration, migrations, and backups, and [Testing](docs/TESTING.md) for fixture commands.

For a free demo deployment, follow the [Render configuration and troubleshooting steps](docs/OPERATIONS.md#render-demo-deployment), including the Python version, build/start commands, and temporary storage limits.

## Data and Privacy

Explore the API with synthetic examples. Protect your configured storage directory: the backend saves uploaded source bytes, analysis evidence, reviews, and audit events there. Treat the configured actor as an audit label, not a verified identity.

## Documentation

### Configure and Operate the API

| Document | Use it to |
| --- | --- |
| [Backend Configuration](docs/CONFIGURATION.md) | Set storage paths, origins, upload limits, and statistical thresholds |
| [Run, Back Up, and Recover DataGuard](docs/OPERATIONS.md) | Manage service startup, migrations, backups, and recovery |

### Work with Your Data

| Guide | Use it to |
| --- | --- |
| [Upload, Analyze, and Version Datasets](docs/INGESTION.md) | Upload files, inspect checks, append versions, and download source data |
| [Validation Rules and Quality Metrics](docs/RULES.md) | Define rule revisions and interpret scores and statistical findings |
| [Review Findings and Correct Data](docs/REVIEW_DATASETS.md) | Record decisions, edit cells, and execute approved replacements |
| [Explore Your Data Quality Workspace](../datagaurd.front-end/docs/WORKSPACE.md) | Work with the browser interface |

### Integrate and Develop

| Reference | Use it to |
| --- | --- |
| [DataGuard API Reference](docs/API.md) | Find routes, request shapes, responses, and error conventions |
| [API Models and Stored Records](docs/DATA_DICTIONARY.md) | Look up records, identifiers, fields, and state values |
| [DataGuard API Architecture](docs/ARCHITECTURE.md) | Trace requests, transactions, and source modules |
| [Backend Testing and Validation](docs/TESTING.md) | Run API, unit, persistence, and analytical checks |
| [Frontend Setup](../datagaurd.front-end/README.md) | Run the companion Vue application |
