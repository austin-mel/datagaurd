# DataGuard backend

## Table of Contents

- [Project Summary](#project-summary)
- [Technologies Used](#technologies-used)
- [Necessary Tools](#necessary-tools)
- [Application Setup](#application-setup)
  - [Set Up the Development Environment](#set-up-the-development-environment)
  - [Back-end Setup](#back-end-setup)
  - [Front-end Setup](#front-end-setup)
  - [Project Root Setup](#project-root-setup)
  - [Verify the Setup](#verify-the-setup)
- [Demo walkthrough](#demo-walkthrough)
- [Development commands](#development-commands)
- [Data and privacy](#data-and-privacy)
- [Documentation](#documentation)

## Project Summary

Use DataGuard's API to assess CSV, TSV, Excel, and Parquet datasets. Profile columns, define dataset-specific rules, calculate row-based quality metrics, identify statistical changes, and record review decisions and corrections.

Preserve your original files and trace each version, rule revision, check attempt, finding, and audit event. Connect the Vue frontend through the versioned workspace API, or use the lower-level endpoints to build ingestion, analysis, history, and approved-remediation workflows.

## Technologies Used

| Technology | Responsibility |
| --- | --- |
| Python 3.12+ | Application and analytical services |
| FastAPI and Uvicorn | HTTP endpoints, OpenAPI documentation, and ASGI server |
| Pydantic and pydantic-settings | Request schemas, configuration, and validation |
| SQLAlchemy, SQLite, and Alembic | Persistent metadata and schema migrations |
| pandas, openpyxl, and PyArrow | Tabular processing and format support |
| PyYAML and defusedxml | Rule configuration and XML parsing support |
| pytest, pytest-cov, HTTPX, and mypy | Automated tests, coverage, API tests, and type checks |
| uv | Dependency management and reproducible environments |

Find dependency ranges in [pyproject.toml](pyproject.toml) and exact resolved versions in [uv.lock](uv.lock).

## Necessary Tools

| Tool | Purpose |
| --- | --- |
| Python 3.12 or newer | Run the API, tests, and administration scripts |
| uv | Install dependencies from the lockfile |
| Git and an editor | Manage source and configuration |
| Node.js and pnpm | Required only for the companion frontend |

Use the embedded SQLite database without installing a separate database server.

## Application Setup

### Set Up the Development Environment

Open the backend checkout and verify the tools:

```powershell
python --version
uv --version
```

If you have not installed uv, run `python -m pip install uv`, then reopen your terminal if necessary to refresh PATH.

### Back-end Setup

1. Install the locked dependencies, including the development group:

   ```powershell
   uv sync --locked
   ```

2. Create the local environment file if it does not already exist:

   ```powershell
   Copy-Item environment/.example.back-end.env environment/back-end.env
   ```

3. Set the storage location and permitted frontend origins in `environment/back-end.env`:

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

Run these commands from the backend root. Use an absolute storage path for managed deployments; relative paths resolve from your process working directory. Consult [Configuration](docs/CONFIGURATION.md) for every setting.

For an existing Windows virtual environment, use `.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload`. On macOS/Linux, the equivalent interpreter is `.venv/bin/python`; use `cp` instead of `Copy-Item` when copying configuration.

### Front-end Setup

In a second terminal:

```powershell
Set-Location ../datagaurd.front-end
pnpm install --frozen-lockfile
pnpm dev
```

Open [DataGuard](http://127.0.0.1:5173) and confirm **Connected to backend · Live data**. The default Vite proxy sends `/api` to port 8000. For overrides, use the frontend's `environment/front-end.env`; see the [frontend README](../datagaurd.front-end/README.md).

### Project Root Setup

```text
datagaurd/
  datagaurd.front-end/   # Vue application and browser tests
  datagaurd.back-end/    # API, migrations, source files, and metadata
```

Install dependencies and configure environment files independently in each project. The parent directory requires no dependency installation or shared environment file.

### Verify the Setup

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/api/v1/upload-policy
uv run pytest
uv run mypy src
```

Confirm that the health endpoint returns `{ "status": "ok" }`. Browse the API using [Swagger UI](http://127.0.0.1:8000/docs), [ReDoc](http://127.0.0.1:8000/redoc), or [OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

## Demo walkthrough

1. Seed the examples and start the API and frontend.
2. Open **County facilities** and inspect its profile, validation findings, and quality scores.
3. Create a custom ruleset and run validation to apply it.
4. Correct a flagged cell, save the new version, and run validation again.
5. Download a version and inspect the dataset history.
6. Upload a synthetic dataset through the frontend or [ingestion API](docs/INGESTION.md).
7. Use the [review and correction endpoints](docs/REVIEW.md) to annotate findings or preview, approve, and execute an exact replacement.

| Dataset | Rows | Columns | Stable ID |
| --- | ---: | ---: | --- |
| County facilities | 20 | 6 | `3be295a2-aad7-4724-9853-44729e762066` |
| Office inventory | 12 | 5 | `8e6483be-d006-4ab9-84c8-e86eac26b997` |
| Customer master | 248,512 | 4 | `9e716851-5f95-4433-b771-d336b0d00d20` |

Use the examples to explore intentional errors and statistical anomalies. You can repeat the seed command without replacing existing source versions or edits. Treat each ordinary upload as a new dataset: the backend assigns a fresh UUID even when the name and content match an earlier upload.

## Development commands

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

## Data and privacy

Explore the API with synthetic examples. Protect your configured storage directory: the backend saves uploaded source bytes, analysis evidence, reviews, and audit events there. Treat the configured actor as an audit label, not a verified identity. Before handling shared or sensitive data, implement authentication, dataset authorization, and tenant isolation as described in [Operations](docs/OPERATIONS.md); the API does not provide those controls through CORS or actor labels.

## Documentation

### Developer references

| Document | Use it to |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Trace startup, requests, persistence, and source ownership |
| [API reference](docs/API.md) | Find every route, request shape, response, and error convention |
| [Data dictionary](docs/DATA_DICTIONARY.md) | Understand records, schemas, identifiers, and state values |
| [Configuration](docs/CONFIGURATION.md) | Configure limits, storage, CORS, and statistical settings |
| [Rules and metrics](docs/RULES.md) | Define rule revisions and interpret validation and statistical results |
| [Testing](docs/TESTING.md) | Run API, unit, persistence, and analytical verification |
| [Operations](docs/OPERATIONS.md) | Manage migrations, backups, recovery, and deployment |

### Workflow guides

| Guide | Use it to |
| --- | --- |
| [Ingestion and analysis](docs/INGESTION.md) | Upload, profile, validate, version, and download datasets |
| [Review and corrections](docs/REVIEW.md) | Record decisions, edit cells, and execute approved remediations |
| [Frontend workspace](../datagaurd.front-end/docs/WORKSPACE.md) | Use the browser interface and interpret its scores |
