# Testing

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Backend testing](../../datagaurd.back-end/docs/TESTING.md)

Run frontend commands from the frontend checkout after `pnpm install --frozen-lockfile`.

## Build and type checks

| Task | Command |
| --- | --- |
| Build and application type-check | `pnpm build` |
| Build only | `pnpm build-only` |
| Application type-check | `pnpm type-check` |
| Application and test type-check | `pnpm type-check:tests` |
| Inspect built output | `pnpm preview` |

Configure application types in [tsconfig.app.json](../tsconfig.app.json) and test types in [tsconfig.tests.json](../tsconfig.tests.json). Run TypeScript checks alongside your tests to catch type errors that test execution can miss.

## Unit, component, and repository tests

```powershell
pnpm test
pnpm test:watch
pnpm test:coverage
```

Add unit tests under `tests/unit/**/*.test.ts`. [vitest.config.ts](../vitest.config.ts) uses Node by default, restores mocks and stubbed globals/environment values, and allows 30 seconds per test. Select a DOM environment for component tests that need browser APIs.

| Test area | Behavior covered |
| --- | --- |
| Validation and syntax | Rule types, malformed/disabled rules, portable patterns, dates, allowed values, row-based scores |
| Data utilities | CSV, identifier resolution, profiles, statistical findings, deterministic samples |
| Repositories | API paths, response contracts, timeouts/errors, source selection, live-write isolation |
| Sample repository | Immutable downloads, versions, corrections, ignores, pending validation |
| Stores and composables | Hydration, response replacement, failed saves, reconciliation, recents |
| Components | Dialogs, profiles, pagination, upload validation, editing, display states |

Use the coverage report to inspect services, stores, composables, utilities, and Vue components, including files without tests. The configuration excludes barrel `index.ts` files and route-level views from the unit percentage; test view workflows with Playwright. Meet the V8 thresholds of **90% statements, 90% lines, 80% branches, and 85% functions**. Find text, HTML, and LCOV reports in `coverage/`.

## Browser tests

```powershell
pnpm exec playwright install chromium firefox webkit
pnpm test:e2e
pnpm test:e2e --project=chromium
pnpm test:e2e:ui
pnpm exec playwright show-report output/playwright/report
```

[playwright.config.ts](../playwright.config.ts) starts its own Vite server at `http://127.0.0.1:4173` with a strict port and no reuse of an existing server. Keep that port free. Its process environment forces `VITE_DATA_SOURCE=api` and `VITE_API_BASE_URL=/api/v1` regardless of local environment files.

| Project | Device profile |
| --- | --- |
| chromium | Desktop Chrome |
| firefox | Desktop Firefox |
| webkit | Desktop Safari |
| mobile-chromium | Pixel 7 |

Use [tests/e2e/](../tests/e2e/) to verify navigation, uploads, rules, validation, edits, ignores, and sample workflows. Supply isolated HTTP fixtures for API workflows and use the real local repository for sample workflows. Treat unexpected routes and uncaught browser errors as failures. You can run these tests without writing to a live backend.

Expect three workers locally and two in CI. CI retries failed tests up to twice; local runs do not retry. Inspect failure screenshots and traces under `output/playwright/test-results/`, and open the HTML report under `output/playwright/report/`.

## Live API parity

**Prerequisites:** a running backend and the three unmodified seeded demos.

```powershell
pnpm test:live
# Optional endpoint override:
$env:API_URL = 'http://127.0.0.1:8000/api/v1'
pnpm test:live
Remove-Item Env:API_URL
```

Run the [live configuration](../vitest.live.config.ts) explicitly to select `tests/live/`. The suite reads workspace projections and downloads, then compares demo row counts, columns, quality dimensions, issue/review/profile counts, metadata, and download row counts against samples. It makes no writes; normal tests and CI do not run it. If you have edited the demos, use fresh isolated storage because reseeding preserves existing versions.

## Continuous integration

Use [tests.yml](../.github/workflows/tests.yml) to verify pushes and pull requests with Node 24 and pnpm 9.12.3. The workflow installs locked dependencies and browsers, builds, type-checks tests, enforces coverage, and runs browser tests. Download coverage and Playwright artifacts within their 14-day retention period.

Use `pnpm test:all` to run unit and browser suites together. Run builds, coverage checks, test type checks, live parity, and backend tests separately.

## Maintain fixtures and contracts

Keep [tests/fixtures/](../tests/fixtures/) aligned with frontend domain types and backend projections. When changing a rule or metric, update both implementations and verify parity. To export updated sample definitions:

```powershell
node --import ./scripts/register.mjs scripts/export-demo-manifest.mjs
Copy-Item output/backend-integration/demo-datasets.json ../datagaurd.back-end/config/demo-datasets.json
```

Keep the exporter invocation above so `scripts/register.mjs` resolves application imports; let Vitest resolve test imports. Review the exported small-sample rows and rules, and keep the large-customer generator specification aligned across both projects. Use fresh storage to verify manifest changes because updating the manifest does not overwrite existing backend versions.
