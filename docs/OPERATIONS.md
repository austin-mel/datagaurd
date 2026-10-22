# Run, Back Up, and Recover DataGuard

[README](../README.md) · [Configuration](CONFIGURATION.md) · [Architecture](ARCHITECTURE.md)

Manage your API service, schema migrations, demo datasets, backups, and recovery procedures.

## Table of Contents

- [Storage layout](#storage-layout)
- [Start and stop](#start-and-stop)
- [Render demo deployment](#render-demo-deployment)
- [Migrations](#migrations)
- [Backup and restore](#backup-and-restore)
  - [Create a consistent backup](#create-a-consistent-backup)
  - [Restore and verify](#restore-and-verify)
- [Demo maintenance](#demo-maintenance)
- [Failure recovery](#failure-recovery)

## Storage layout

```text
storage/
  metadata.sqlite3          # SQLAlchemy records and stored JSON evidence
  metadata.sqlite3-wal      # SQLite write-ahead log when present
  metadata.sqlite3-shm      # SQLite shared-memory coordination when present
  files/
    <file-id>.csv           # Immutable version files
    <file-id>.tsv
    <file-id>.xlsx
    <file-id>.parquet
```

Protect the entire configured storage directory. Keep its database and source files together because database rows reference files by ID and hash. Choose a durable location outside application build directories, restrict access to your service/operator accounts, and use a filesystem that supports hard links.

## Start and stop

Start a development server with:

```powershell
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

Keep the terminal running while you use the API. Press Ctrl+C to stop the server.

## Render demo deployment

Render's Free Web Service can run the current SQLite backend for demos. Its filesystem is ephemeral: database changes and uploaded files are lost on redeploy, restart, or idle spin-down. Free services cannot attach a persistent disk. See [Render's free service limits](https://render.com/docs/free).

Push the backend branch, including `.python-version`, `pyproject.toml`, and `uv.lock`, to GitHub. Configure the Render service with:

| Setting | Value |
| --- | --- |
| Runtime / Language | Python 3 |
| Branch | `apps.back-end` |
| Root directory | Leave blank; this branch contains the backend at its repository root |
| Instance type | Free |
| Health check path | `/health` |

The root `.python-version` selects Python 3.12. Remove a conflicting `PYTHON_VERSION` environment variable in Render because it takes precedence over the file. See [Python version selection](https://render.com/docs/python-version).

Use this **build command**:

```bash
python -m pip install --upgrade uv && python -m uv sync --locked --no-dev
```

Use this **start command**:

```bash
.venv/bin/python -m uvicorn src.main:app --host 0.0.0.0 --port $PORT --workers 1
```

The build installs uv from PyPI and invokes it as a Python module, bypassing Render's `uv` command wrapper. Application dependencies remain pinned by `uv.lock`. The start command uses the environment created by the build and does not invoke uv. Keep `$PORT` as written so Render supplies its listening port.

Set these values in Render's Environment section:

| Variable | Value |
| --- | --- |
| `DATAGUARD_STORAGE_DIR` | `storage` |
| `DATAGUARD_CORS_ORIGINS` | `["https://your-frontend-domain"]`, replacing the placeholder with the frontend's origin |
| `DATAGUARD_ACTOR` | `local_operator` |

Process environment variables take precedence over `environment/.back-end.env`; the local dotenv file does not need to be committed or uploaded. Leave `UV_PROJECT_ENVIRONMENT` unset so the build creates `.venv`, matching the start command. The service initializes SQLite, applies migrations, and loads `src/data/facilities_dirty.csv` with its facilities rules at startup. The connected workspace therefore starts with a validated 150-row example, including after ephemeral storage is reset. Existing versions and edits are preserved. Set `DATAGUARD_SEED_DEFAULT_DATASET=false` to disable this behavior; disabling it does not delete an existing example.

For an existing service, update the build/start commands in its Settings page. Check that Runtime is Python: [Render's runtime-change instructions](https://render.com/docs/native-runtimes#changing-a-services-runtime) describe Settings > Build > Source > Edit. Adding files to the repository does not change an existing service's runtime or Dashboard commands. After pushing the changes, choose **Manual Deploy > Clear build cache & deploy**. Confirm that the build selects Python 3.12 and that `/health` returns `{"status":"ok"}`.

For `/home/render/envwrappers/uv: ... uv: command not found`, use the build/start commands above; this failure occurs in Render's tool bootstrap before application dependencies are installed. The subsequent build and health check must still succeed to confirm deployment.

## Migrations

Inspect and apply schema migrations with these commands. The service also upgrades to Alembic head at startup:

```powershell
uv run alembic current
uv run alembic upgrade head
uv run alembic current
```

Stop writers and back up storage before migration. Configure Settings for [migrations/env.py](../src/migrations/env.py), or supply an existing connection when invoking migrations programmatically.

| Revision | Purpose |
| --- | --- |
| `0001_current` | Complete current schema: datasets, versions, checks, findings, audit, reviews, remediations, rulesets, and cell-review state |

Use `0001_current` to initialize a new workspace with dataset and check-run rule assignments. Keep the database on the migration revision supported by your application checkout.

For development storage created with the previous migration chain, stop the API and set `DATAGUARD_STORAGE_DIR` to a new, empty directory before starting or seeding. The old revisions are no longer upgrade targets; do not stamp an old database with the new baseline. Keep any source files you want to upload into the new workspace. The application does not convert or delete the old storage directory.

## Backup and restore

### Create a consistent backup

1. Stop the API and any administrative writers.
2. Determine the actual resolved storage directory from configuration.
3. Copy the **entire directory** to a fresh backup location, including source files and any SQLite sidecars.
4. Record the application revision, environment configuration, rule files, and migration revision alongside the snapshot.
5. Verify a restore using a separate directory before relying on the backup.

From the backend root, stop the service and back up the default storage location with:

```powershell
$sourceStorage = (Resolve-Path -LiteralPath ./storage).Path
$backupDirectory = Join-Path $env:USERPROFILE ('DataGuardBackups/' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backupDirectory -ErrorAction Stop | Out-Null
Copy-Item -LiteralPath $sourceStorage -Destination (Join-Path $backupDirectory 'storage') -Recurse -ErrorAction Stop
```

Stop writers before copying storage so you retain WAL transactions and the matching source-file set. If you need online backups, implement coordinated database/file snapshots; the application does not provide a complete online-backup command.

### Restore and verify

1. Keep the service stopped and preserve the existing storage directory.
2. Copy a backup into a **new** restore directory. Do not combine it with files from a different database snapshot.
3. Point `DATAGUARD_STORAGE_DIR` at that restored directory and use a compatible application revision.
4. Start the API; check health, catalog, migrations, and representative version downloads.
5. Confirm hashes, version/run histories, assigned rules, and review/remediation state before switching clients.

Restore matching database and files before starting, and retain your untouched backup. Startup reconciliation deletes managed files that the restored database does not reference.

## Demo maintenance

```powershell
uv run python -m src.scripts.seed_demo
```

Run the seed command to add missing examples from `config/demo-datasets.json` using stable UUIDs and the deterministic customer generator. Reruns preserve existing versions and edits and can retry failed demo checks. To start with clean demos, use an unused storage directory as described in [Configuration](CONFIGURATION.md#isolated-development-storage); the seed command has no reset option.

Update the sample definitions and rules in both projects, then run these commands from the sibling frontend checkout:

```powershell
node --import ./scripts/register.mjs scripts/export-demo-manifest.mjs
Copy-Item output/backend-integration/demo-datasets.json ../datagaurd.back-end/config/demo-datasets.json
```

Follow [Frontend Testing and API Integration](../../datagaurd.front-end/docs/TESTING.md#maintain-fixtures-and-contracts) to verify the shared demo contract. Use fresh storage to check the revised examples because a manifest update preserves existing persisted versions.

## Failure recovery

| Symptom | Recovery |
| --- | --- |
| Invalid startup configuration | Fix environment values or YAML; the service validates rules before serving requests |
| Database unavailable/locked | Check storage permissions, disk capacity, competing writers, and SQLite timeout; inspect logs |
| File integrity error | Preserve evidence, compare expected hash, and restore the matching source from a consistent backup |
| Upload response lost | Inspect the dataset catalog and version/check IDs before repeating the upload |
| Saved check has failed | Correct the underlying cause, then POST `/versions/{id}/check` for a new attempt |
| Workspace validation uncertain | GET the current dataset before retrying; the check may have committed |
| Cell edit conflict | Fetch current dataset/version/group and review the intended change again |
| Remediation response lost | GET proposal state; repeated execution of an executed proposal returns the same result |
| Corrected version saved but analysis failed | Preserve correction; retry the result version's check |
| Running check remains after process interruption | Inspect run and service logs; there is no automatic startup requeue or public generic resume route |

To resume an interrupted ordinary run, stop competing processing, back up storage, and call `Catalog.process_check(run_id)` with its recorded ID. The method resumes only a running attempt and checks the recorded implementation version. For an executed remediation, repeat execution to resume its check through the API. Preserve the attempt history and let validation determine the result.
