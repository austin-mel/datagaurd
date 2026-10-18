# Configuration

[README](../README.md) · [Rules](RULES.md) · [Operations](OPERATIONS.md)

## Loading and precedence

Configure the backend in `environment/back-end.env` relative to the project root. [Settings](../src/settings.py) gives process environment variables precedence and uses defaults for omitted values. Prefix supported names with `DATAGUARD_`; Settings ignores unknown dotenv entries. Restart the server after changing configuration.

Use the default absolute paths beneath the project root, or supply your own paths. When you configure a relative value such as `DATAGUARD_STORAGE_DIR=storage`, run commands from the backend root so the process resolves it correctly. Prefer absolute paths when your service uses another working directory.

## Service settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATAGUARD_STORAGE_DIR` | Project-root `storage/` | SQLite metadata and immutable files |
| `DATAGUARD_RULES_PATH` | Project-root `config/generic.yaml` | Default YAML rules loaded at startup |
| `DATAGUARD_ACTOR` | `local_operator` | Nonempty audit/check actor label |
| `DATAGUARD_REFERENCE_DATE` | Unset | ISO date; when unset, resolve the server's local calendar date per check |
| `DATAGUARD_CORS_ORIGINS` | `["http://127.0.0.1:5173","http://localhost:5173"]` | JSON list of permitted browser origins |

Set the reference date when you need reproducible check context; each run records it. Configure explicit date bounds in selected-date rules because they do not substitute this setting. Use GET, POST, PUT, and OPTIONS with CORS, send Content-Type and Authorization headers as needed, and read Content-Disposition for downloads. Implement authentication separately; permitting the Authorization header does not validate it.

## Resource limits

| Variable | Default | Constraint |
| --- | ---: | --- |
| `DATAGUARD_MAX_UPLOAD_BYTES` | 104,857,600 (100 MiB) | Positive; original upload bytes |
| `DATAGUARD_MAX_ROWS` | 500,000 | Positive; data rows |
| `DATAGUARD_MAX_COLUMNS` | 1,000 | Positive; headers/columns |
| `DATAGUARD_MAX_CELLS` | 2,000,000 | Positive; row-by-column cells |
| `DATAGUARD_MAX_DECODED_BYTES` | 209,715,200 (200 MiB) | Positive; expanded/decoded data |

Size your inputs against every limit: a dataset can fit the row limit and still exceed the cell limit. Allow corrected CSV snapshots to fit the decoded-byte bound, which governs those snapshots. Fetch `/api/v1/upload-policy` to read effective limits and supported extensions.

## Statistical and evidence settings

| Variable | Default | Constraint/meaning |
| --- | ---: | --- |
| `DATAGUARD_STATISTICAL_MIN_SAMPLES` | 20 | At least 1; usable values/records for applicable analyses |
| `DATAGUARD_IQR_MULTIPLIER` | 1.5 | Finite, nonnegative IQR fence multiplier |
| `DATAGUARD_MISSINGNESS_INCREASE_PERCENTAGE_POINTS` | 5 | 0–100; flag increases strictly above this threshold |
| `DATAGUARD_ROW_COUNT_CHANGE_PERCENTAGE` | 20 | Finite, nonnegative relative change threshold |
| `DATAGUARD_CATEGORY_SHARE_CHANGE_PERCENTAGE_POINTS` | 10 | 0–100; largest category-share shift threshold |
| `DATAGUARD_FINDING_SAMPLE_SIZE` | 20 | 1–1,000; bounded finding/preview samples |
| `DATAGUARD_TOP_CATEGORY_COUNT` | 5 | 1–100; profile top-category count |

Supply a ruleset's optional `statistics` object to override its five analytical thresholds. Specify every threshold you want to preserve: omitted fields use the object's model defaults rather than process settings. Use sample limits to bound displayed evidence while retaining complete affected-record membership. Inspect each stored run's configuration and effective settings to reproduce its analysis.

## Example configuration

Adapt these paths, origins, and limits to your environment:

```dotenv
DATAGUARD_STORAGE_DIR=C:/DataGuard/development-storage
DATAGUARD_RULES_PATH=config/generic.yaml
DATAGUARD_ACTOR=development_operator
DATAGUARD_CORS_ORIGINS=["http://127.0.0.1:5173"]
DATAGUARD_MAX_UPLOAD_BYTES=104857600
DATAGUARD_MAX_ROWS=500000
DATAGUARD_MAX_COLUMNS=1000
DATAGUARD_MAX_CELLS=2000000
DATAGUARD_MAX_DECODED_BYTES=209715200
```

To change an existing dataset's rules, create a revision and assign it explicitly. Changing the default rules alone preserves existing assignments and historical runs.

## Isolated development storage

Set an unused directory before running administrative commands or the server:

```powershell
$env:DATAGUARD_STORAGE_DIR = Join-Path $env:TEMP ('dataguard-demo-' + [guid]::NewGuid().ToString('N'))
uv run python -m src.scripts.seed_demo
uv run uvicorn src.main:app --host 127.0.0.1 --port 8000
# After stopping the server:
Remove-Item Env:DATAGUARD_STORAGE_DIR
```

Use the same environment in your seeding and server processes. Retain the chosen directory for as long as you need its data. Run parity checks there to preserve your ordinary storage.
