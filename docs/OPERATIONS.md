# Operations

[README](../README.md) · [Configuration](CONFIGURATION.md) · [Architecture](ARCHITECTURE.md)

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

For a managed single-process service, omit `--reload`, use an absolute storage path, and bind behind the intended reverse proxy. Configure process supervision to capture Uvicorn/application logs and perform orderly shutdown. Startup applies migrations and file reconciliation, so deploy against a backed-up, consistent storage snapshot.

Use a single service process unless you implement coordination for shared-storage reconciliation and long-running checks. SQLite's write lock does not supply a job queue or multi-worker recovery protocol.

## Migrations

Apply migrations during a controlled deployment with these commands. The service also upgrades to Alembic head at startup:

```powershell
uv run alembic current
uv run alembic upgrade head
uv run alembic current
```

Stop writers and back up storage before migration. Configure Settings for [migrations/env.py](../src/migrations/env.py), or supply an existing connection when invoking migrations programmatically.

| Revision | Purpose |
| --- | --- |
| `0001_current` | Complete current schema: datasets, versions, checks, findings, audit, reviews, remediations, rulesets, and cell-review state |

The current baseline creates a new workspace directly, with required dataset and check-run rule assignments. Dataset IDs are UUIDs at creation. Only the current rule definitions and analysis payloads are supported.

For development storage created with the previous migration chain, stop the API and set `DATAGUARD_STORAGE_DIR` to a new, empty directory before starting or seeding. The old revisions are no longer upgrade targets; do not stamp an old database with the new baseline. Keep any source files you want to upload into the new workspace. The application does not convert or delete the old storage directory.

## Backup and restore

### Create a consistent backup

1. Stop the API and any administrative writers.
2. Determine the actual resolved storage directory from configuration.
3. Copy the **entire directory** to a fresh backup location, including source files and any SQLite sidecars.
4. Record the application revision, environment configuration, rule files, and migration revision alongside the snapshot. Store configuration appropriately if it contains private deployment details.
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

Export the manifest with the frontend's `scripts/export-demo-manifest.mjs`, then copy its JSON into backend `config/demo-datasets.json` after updating samples and rules in both projects. Use fresh storage to check the revised examples because a manifest update preserves existing persisted versions.

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

## Production readiness

Complete the work below for your deployment before accepting shared or sensitive data:

| Area | Required deployment work |
| --- | --- |
| Identity and access | Authenticate requests, authorize dataset/workspace access, enforce ownership, derive audit actor from verified identity |
| Network | Terminate HTTPS, restrict exposure, configure exact origins, preserve API paths, align proxy body/time limits with application limits |
| Persistence | Provision durable storage with hard-link support, access controls, capacity monitoring, tested backups, and restore procedures |
| Concurrency | Coordinate migration/reconciliation, define process topology, add conditional ruleset writes and broader write idempotency |
| Scale | Replace eager workspace loading with paginated summaries/details, cache immutable analysis, design asynchronous job execution |
| Contract evolution | Define supported evidence schemas and strengthen explicit workspace response models |
| Observability | Collect request/error logs, monitor storage health and failed/stuck runs, and set recovery objectives |
| Data lifecycle | Define retention/export/deletion policies; no dataset-delete API or automated retention process currently exists |

Size and operate your deployment around synchronous analysis and SQLite/local-file storage. Verify access controls, backup recovery, and concurrency behavior independently of frontend builds and process-health checks.
