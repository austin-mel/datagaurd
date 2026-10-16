# DataGuard frontend and REST integration

The Vue frontend loads its workspace from the FastAPI backend at `/api/v1`. Dataset metadata, scores, profiles, rules, findings, cell review and history come from the backend. Uploads, downloads, ruleset saves, corrections and revalidation use the same repository.

## Start development

In `C:\Users\Austin\Desktop\Everything\Coding\datagaurd\datagaurd.back-end`:

```powershell
.\.venv\Scripts\python.exe -m src.scripts.seed_demo
.\.venv\Scripts\python.exe -m uvicorn src.main:app --host 127.0.0.1 --port 8000 --reload
```

In this frontend project:

```powershell
pnpm dev
```

Open <http://127.0.0.1:5173>. Interactive API documentation is at <http://127.0.0.1:8000/docs>.

Vite proxies `/api` to `http://127.0.0.1:8000`. Optional configuration: copy `environment/.example.front-end.env` to `environment/front-end.env`, edit, and restart Vite. `VITE_API_BASE_URL` can point at another API's `/api/v1`; `BACKEND_PROXY_TARGET` changes the development proxy; `VITE_DATA_SOURCE=seeded` explicitly selects the demo workspace. These frontend values are public, so do not store secrets in them.

For separate frontend/backend origins, configure the backend's `DATAGUARD_CORS_ORIGINS` as a JSON array of approved origins. Both localhost:5173 and 127.0.0.1:5173 are permitted by default. Production hosting must route `/api` to FastAPI or configure an absolute API URL; the Vite development proxy is not part of the built site.

## Data source behavior

- On initial load, a reachable backend is authoritative, including an empty dataset catalog.
- Network failures/timeouts and unavailable gateway responses select the complete seeded workspace. Vite's empty upstream-error response is recognized too.
- The banner identifies live data or sample data. Sample changes last only for the browser session. Reconnect reloads the page and discards those sample edits.
- Authentication, validation, missing-route, malformed-contract and structured backend errors are shown instead of hidden with sample values.
- Once live data is selected, a failed write is never replayed against samples. Reload to select backup data after a later outage. Revalidation errors reconcile with the server because a request may commit before its connection fails.
- File uploads require a live connection and the backend's upload policy. They are disabled in sample mode. Demo downloads, rules, review and revalidation work locally.

## Example datasets

| Example | Size | Rows | Columns | Backend ID |
| --- | --- | ---: | ---: | --- |
| County facilities | Small | 20 | 6 | `3be295a2-aad7-4724-9853-44729e762066` |
| Office inventory | Small | 12 | 5 | `8e6483be-d006-4ab9-84c8-e86eac26b997` |
| Customer master | Large | 248,512 | 4 | `9e716851-5f95-4433-b771-d336b0d00d20` |

`dataset.id` **is** the UUID primary key; there is no separate dataset UUID field. Names and original filenames are display metadata and may repeat. New uploads always receive fresh random UUIDs, even when their name and contents match another upload. The frontend routes, store, recent history, and API mutations use this ID; UUIDs are not displayed in the interface. URLs retain the form `/?dataset=<uuid>` and download filenames remain human-readable.

Migration `0006` remaps existing non-UUID primary keys and their version, audit and remediation references without replacing source files or validation history. Already-valid UUIDs remain unchanged. Old sample bookmarks are redirected to their UUID URL, and saved recent visits are migrated. For an explicit backup plus migration in the backend project, run `.\.venv\Scripts\python.exe -m src.scripts.migrate_dataset_ids`.

These contain actual generated records, including deliberate missing IDs, duplicates, invalid ranges and statistical anomalies. Their profiles, scores and review membership are calculated from those records. The backend seed command preserves existing records and is safe to rerun without duplicating the examples. It is an explicit development command, never an automatic production startup step.

The existing 150-row `facilities_clean.csv` was preserved, so the current live catalog has **four** datasets. Its retired date rules were migrated by appending a compatible rule revision and new check; the old source bytes, rules and runs remain intact. The original recorded date cutoff was retained. The offline catalog has exactly the three examples above.

The backend's `config/demo-datasets.json` contains the frontend's exported small rows and rules. The customer generator uses the same deterministic specification in both projects. To regenerate the manifest after changing examples:

```powershell
node --import ./tests/register.mjs scripts/export-demo-manifest.mjs
Copy-Item output/backend-integration/demo-datasets.json ../datagaurd.back-end/config/demo-datasets.json
```

Existing seeded versions are intentionally preserved; changing a manifest does not overwrite them.

## REST contract

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/api/v1/workspace` | Complete current dataset projections and rule-editor catalog |
| GET | `/api/v1/upload-policy` | Supported extensions and resource limits |
| POST | `/api/v1/datasets` | Multipart `file` and optional `sheet_name`; persist and validate; returns 201 |
| GET | `/api/v1/datasets/{id}` | Refresh a current dataset |
| PUT | `/api/v1/datasets/{id}/ruleset` | Save the editor's custom ruleset |
| POST | `/api/v1/datasets/{id}/validation` | Validate using `{ "version": "v1" }` |
| POST | `/api/v1/datasets/{id}/cell-reviews` | Version-scoped replace, delete-row or ignore action |
| GET | `/api/v1/datasets/{id}/file?version=v1` | Download the exact version's source bytes |

The original lower-level API routes remain available. Errors use `{ "error": { "code", "message", "details" } }`. The frontend validates workspace, dataset and upload-policy responses before storing them. The current UI projection returns all groups/history; it does not silently truncate them.

## Verification

```powershell
pnpm build
pnpm test
# With both servers running and unmodified demo datasets:
node --import ./tests/register.mjs scripts/verify-live.mjs
```

Backend checks:

```powershell
.\.venv\Scripts\python.exe -m pytest src/tests/test_workspace_api.py src/tests/test_dataset_identity.py
.\.venv\Scripts\python.exe -m mypy src
.\.venv\Scripts\python.exe -m pytest
```

UUID update verification on October 15, 2026:

- Six focused backend tests pass, including independent uploads with identical filenames and preservation of related records during UUID migration. Mypy passes across 62 source files.
- The existing database migration preserved all four datasets, four versions, five checks and 19 audit events, with no foreign-key violations. A SQLite backup was created before migration.
- Frontend UUID regression tests were added. The frontend build/test command was declined, so frontend checks and browser verification have not been rerun for this update.

Earlier REST integration verification on October 15, 2026 (before the UUID update):

- Production frontend build and Vue/TypeScript check pass; five frontend integration tests pass.
- Four new backend integration tests pass; mypy passes across all 59 source files.
- Real browser checks verified all four live detail pages, rendered scores, columns, metadata, history and review sections, with no application JavaScript errors.
- With the backend stopped, all three seeded detail pages populated successfully, including the large customer dataset.
- Isolated browser test: upload CSV, download original, correct duplicate ID into v2, revalidate to 100%, save custom rules, and confirm persistence after page/backend reload. Temporary test data was kept outside real backend storage.
- Live/offline demo score, issue-count, review-group and download-row-count parity passes. Seed reruns report all three examples already present.
- Full backend suite: **202 passed, 13 failed**. The same 13 failures occur on the unchanged committed backend (198 passed before adding four integration tests). Existing failures concern numeric prerequisite semantics, no-op revalidation assumptions, identifier outlier behavior, fixture line endings/counts, and outdated upload-limit/implementation-version assertions. They are not claimed as resolved.

Screenshots from the verification are in `output/playwright/live-datasets.png` and `output/playwright/offline-datasets.png` (ignored local artifacts).

## Remaining work before production

| Area | Frontend update | Backend/schema update |
| --- | --- | --- |
| Identity and permissions | Login/session, permission-aware actions and expired-session handling. | Authenticate every route; authorize dataset access; add workspace/owner identifiers. Derive audit actor from verified identity instead of `local_operator`. |
| Large workspaces | Fetch catalog summaries first; load detail on selection; paginate history/findings/cells and provide loading/progress UI. Move large offline calculation off the main thread if demo performance matters. | Replace eager full-workspace projection with paginated summaries and detail endpoints. Current reads reparse source files and return all review groups. Cache immutable profiles/review projections and expose asynchronous validation jobs with status/progress. |
| Safe concurrent edits | Refresh on conflicts and let users compare/reapply unsaved rules. | Add expected rule revision/version or ETag preconditions for ruleset assignment and idempotency keys for uploads/writes. Cell edits already check source version; ruleset saves can currently overwrite a concurrent assignment. |
| Schema evolution | Generate request/response types from a versioned contract and retain response validation. | Replace generic JSON projection responses with explicit Pydantic workspace/dataset DTOs. Version stored result/rule schemas and add backward-compatible readers. Legacy evidence is preserved, but old typed history endpoints can still reject retired rule kinds; the migration repairs current assignments/runs rather than rewriting archived evidence. |
| Complete analytical context | Add views for full statistical results, thresholds/baselines, all historical versions and structured processing failures when those workflows are needed. Show source size/format/sheet, dataset owner and descriptive metadata. | Expose the currently unused statistical analysis/threshold/baseline fields in UI DTOs; add owner/description/tags and provenance fields where appropriate. Keep unavailable metrics explicitly unavailable. |
| Operations | Decide whether production demo fallback should remain enabled and retain the visible sample banner. Add retry/recovery guidance for failed operations. | Configure HTTPS, production origins/proxy, request limits, backups, migration deployment, monitoring and durable storage. SQLite/local files and synchronous validation suit local development; choose production persistence/worker topology for your concurrency and recovery needs. |
| Regression baseline | Keep live/offline parity checks and browser workflows in CI. | Resolve the 13 existing failures against the intended validation semantics and refresh the corresponding fixtures; keep schema migration tests. |

The integration is working locally. This checklist describes the remaining production work; it is not a claim that the current application is production-ready.
