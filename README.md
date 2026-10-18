# DataGuard frontend

## Table of Contents

- [Project Summary](#project-summary)
- [Technologies Used](#technologies-used)
- [Necessary Tools](#necessary-tools)
- [Application Setup](#application-setup)
  - [Front-end Setup](#front-end-setup)
  - [Back-end Setup](#back-end-setup)
  - [Project Root Setup](#project-root-setup)
  - [Verify the Setup](#verify-the-setup)
- [Demo walkthrough](#demo-walkthrough)
- [Development commands](#development-commands)
- [Data and privacy](#data-and-privacy)
- [Documentation](#documentation)

## Project Summary

Use DataGuard to assess and improve your tabular data. Upload CSV, TSV, Excel, or Parquet files; inspect profiles and row-based quality scores; customize validation rules; review flagged cells; and preserve source versions and validation history.

Connect the Vue application to its FastAPI backend to save your work, or select the sample workspace to explore synthetic data. If the initial API connection fails, the application opens the sample workspace. Check the banner to identify your data source. You can open the workspace without signing in.

## Technologies Used

| Technology | Responsibility |
| --- | --- |
| Vue 3 and TypeScript | Single-file components and typed application logic |
| Vue Router and Pinia | Navigation and workspace state |
| Vite and Tailwind CSS | Development server, production bundle, and styles |
| Vitest and Vue Test Utils | Unit, component, store, and repository tests |
| Playwright | Desktop and mobile browser workflows |
| FastAPI, Pydantic, SQLAlchemy, SQLite | Companion API, validation, and persistent metadata |

Find dependency ranges in [package.json](package.json) and exact resolved versions in [pnpm-lock.yaml](pnpm-lock.yaml).

## Necessary Tools

| Tool | Requirement |
| --- | --- |
| Node.js | Install `^22.18.0` or `>=24.12.0` to satisfy `package.json` |
| pnpm | CI uses 9.12.3; use the same version for reproducible installs |
| Python | 3.12 or newer, for the backend only |
| uv | Backend dependency synchronization using uv.lock |
| Git and an editor | Source control and editing |
| Playwright browsers | Install the browsers before running browser tests |

Open the frontend checkout in your editor before beginning setup.

## Application Setup

### Front-end Setup

Run commands from this frontend directory:

~~~powershell
node --version
pnpm --version
pnpm install --frozen-lockfile
~~~

If you have not installed pnpm, run `npm install -g pnpm@9.12.3` to match CI.

Use the defaults to request `/api/v1` through Vite's `/api` proxy at `http://127.0.0.1:8000`. To override those defaults, create the local environment file if you do not already have one:

~~~powershell
Copy-Item environment/.example.front-end.env environment/front-end.env
~~~

Edit **environment/front-end.env**:

~~~dotenv
VITE_API_BASE_URL=/api/v1
VITE_DATA_SOURCE=api
BACKEND_PROXY_TARGET=http://127.0.0.1:8000
~~~

For a frontend-only demo, change VITE_DATA_SOURCE to seeded. Start the server:

~~~powershell
pnpm dev
~~~

Open [DataGuard](http://127.0.0.1:5173). Keep the terminal running; use Ctrl+C to stop it. Restart Vite after changing environment values.

### Back-end Setup

In a second terminal, start in the sibling backend checkout:

~~~powershell
Set-Location ../datagaurd.back-end
uv sync --locked
Copy-Item environment/.example.back-end.env environment/back-end.env
uv run python -m src.scripts.seed_demo
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
~~~

Skip the copy if you already have a local configuration. Omit the seed command to start with an empty catalog. The backend creates storage and applies migrations when you start it. You can rerun seeding without replacing existing demo datasets or edits; allow time for the large customer example to validate.

If you already installed dependencies in `.venv`, start the API on Windows with:

~~~powershell
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
~~~

See the [backend README](../datagaurd.back-end/README.md) for configuration, persistence, API examples, and operations.

### Project Root Setup

Keep the projects as sibling directories:

~~~text
datagaurd/
  datagaurd.front-end/   # pnpm, Vue, browser tests
  datagaurd.back-end/    # uv, FastAPI, SQLite, Python tests
~~~

Install dependencies and configure the `environment/` directory separately in each project. Run this README's commands from the frontend unless a step directs you to the backend. On macOS/Linux, use `cd` and `cp` in place of PowerShell's `Set-Location` and `Copy-Item`; use the same `pnpm` and `uv run` commands.

### Verify the Setup

With the backend running:

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/health
~~~

Confirm `status: ok`, then check that the browser banner reads **Connected to backend · Live data**. If your live catalog is empty, upload a dataset or run the seed command. Browse API schemas through [Swagger UI](http://127.0.0.1:8000/docs), [ReDoc](http://127.0.0.1:8000/redoc), or [OpenAPI JSON](http://127.0.0.1:8000/openapi.json).

From the frontend:

~~~powershell
pnpm build
pnpm test
pnpm type-check:tests
pnpm exec playwright install chromium firefox webkit
pnpm test:e2e
~~~

See [Testing](docs/TESTING.md) for coverage reports, browser profiles, and live API verification.

## Demo walkthrough

1. Select explicit sample mode, or seed the backend and use live mode. Confirm the banner before making changes.
2. Open **Datasets**, search for **County facilities**, and open its overview.
3. Inspect completeness, validity, uniqueness, column profiles, validation issues, and history.
4. Open the quality rules, create a custom ruleset, and save a changed rule.
5. Select **Run Dataset Validation** to apply pending changes.
6. Open a flagged cell, review the before/after preview, and replace its value or remove its row. Save, then run validation again.
7. Download the current version. Live edits persist in the backend; sample edits disappear on reload.
8. In live mode, use **Connect a new data source** to upload a synthetic file and validate it.

| Sample | Rows | Columns | Stable dataset ID |
| --- | ---: | ---: | --- |
| County facilities | 20 | 6 | 3be295a2-aad7-4724-9853-44729e762066 |
| Office inventory | 12 | 5 | 8e6483be-d006-4ab9-84c8-e86eac26b997 |
| Customer master | 248,512 | 4 | 9e716851-5f95-4433-b771-d336b0d00d20 |

Use the samples to explore missing values, duplicates, invalid values, and statistical anomalies. Upload your own datasets to add them to a live workspace.

## Development commands

| Task | Command |
| --- | --- |
| Development server | pnpm dev |
| Build and type-check | pnpm build |
| Build only / application type-check | pnpm build-only / pnpm type-check |
| Preview dist/ | pnpm preview |
| Unit tests / watch | pnpm test / pnpm test:watch |
| Coverage / test type-check | pnpm test:coverage / pnpm type-check:tests |
| Browser tests / test explorer | pnpm test:e2e / pnpm test:e2e:ui |
| Unit and browser suites | pnpm test:all |
| Read-only live demo parity | pnpm test:live |

Configure your deployed site's API routing as described in [Configuration](docs/CONFIGURATION.md#production-hosting).

## Data and privacy

Use synthetic samples to explore the workspace. Reloading clears your sample edits; the browser saves only your three most recent dataset visits in local storage. Connect to the backend to persist files, rules, results, and audit history.

Before using sensitive or shared data, configure the access controls described in [backend Operations](../datagaurd.back-end/docs/OPERATIONS.md#production-readiness). The application does not authenticate users, authorize dataset access, or isolate tenants. Treat `local_operator` as a configured audit label, not a verified identity.

## Documentation

### Developer references

| Document | Use it to |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Trace navigation, stores, repositories, fallback, and source ownership |
| [Data dictionary](docs/DATA_DICTIONARY.md) | Look up frontend fields, state values, IDs, and request shapes |
| [Configuration](docs/CONFIGURATION.md) | Configure environments, API routing, deployment, and troubleshooting |
| [Testing](docs/TESTING.md) | Run unit, component, browser, and live parity checks |
| [Backend documentation](../datagaurd.back-end/README.md) | Set up the API and find its full reference |

### Workflow guides

| Guide | Use it to |
| --- | --- |
| [Workspace](docs/WORKSPACE.md) | Navigate datasets and interpret scores and validation state |
| [Datasets and cell review](docs/DATASETS.md) | Upload, download, correct, delete rows, and ignore findings |
| [Quality rules](docs/QUALITY_RULES.md) | Create custom rules and understand matching semantics |
