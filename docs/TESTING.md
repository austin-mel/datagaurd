# Frontend Testing and API Integration

[README](../README.md) · [Architecture](ARCHITECTURE.md) · [Backend testing](../../datagaurd.back-end/docs/TESTING.md)

Run frontend commands from the frontend checkout after `pnpm install --frozen-lockfile`.

## Table of Contents

- [Build](#build)
- [Unit, component, and repository tests](#unit-component-and-repository-tests)
- [Browser tests](#browser-tests)
- [Continuous integration](#continuous-integration)
- [Maintain fixtures and contracts](#maintain-fixtures-and-contracts)

## Build

| Task | Command |
| --- | --- |
| Production build | `pnpm build` |
| Inspect built output | `pnpm preview` |

Configure application types in [tsconfig.app.json](../tsconfig.app.json) and Playwright test types and import resolution in [tsconfig.tests.json](../tsconfig.tests.json). The build bundles the application with Vite; it does not run a separate TypeScript check.

## Unit, component, and repository tests

```powershell
pnpm test:unit
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
| Workspace views | Selection and recents, failed edits, explicit validation, polling cleanup, downloads, upload policy, and retries through the real stores |

## Browser tests

```powershell
pnpm exec playwright install chromium firefox webkit
pnpm test:e2e
pnpm test:e2e --project=chromium
pnpm exec playwright show-report output/playwright/report
```

[playwright.config.ts](../playwright.config.ts) starts its own Vite server at `http://127.0.0.1:4173` with a strict port and no reuse of an existing server. Keep that port free. The Vite application still uses `/dataguard/`; use that prefix when opening the test server manually or writing browser navigation paths. API fixtures continue to match `/api/v1` requests. Its process environment forces `VITE_DATA_SOURCE=api` and `VITE_API_BASE_URL=/api/v1` regardless of local environment files.

[routing.spec.ts](../tests/e2e/routing.spec.ts) simulates GitHub Pages by returning the custom `404.html` with a 404 status for direct route requests. It checks recovery through the app root, exact query/hash preservation, refresh, and Back navigation; ordinary Vite navigation alone would hide this hosting failure.

| Project | Device profile |
| --- | --- |
| chromium | Desktop Chrome |
| firefox | Desktop Firefox |
| webkit | Desktop Safari |
| mobile-chromium | Pixel 7 |

Use [tests/e2e/](../tests/e2e/) to verify navigation, uploads, rules, validation, edits, ignores, and sample workflows. Supply isolated HTTP fixtures for API workflows and use the real local repository for sample workflows. Treat unexpected routes and uncaught browser errors as failures. You can run these tests without writing to a live backend.

Expect three workers locally and two in CI. CI retries failed tests up to twice; local runs do not retry. Inspect failure screenshots and traces under `output/playwright/test-results/`, and open the HTML report under `output/playwright/report/`.

## Continuous integration

Configure your CI runner with a Node version supported by [package.json](../package.json) and pnpm 10. Add your workflow under `.github/workflows/` if you use GitHub Actions; this checkout does not include a workflow.

Run these checks after installing dependencies:

```powershell
pnpm install --frozen-lockfile
pnpm exec playwright install --with-deps chromium firefox webkit
pnpm build
pnpm test
```

Set `CI=true` on your runner to enable the Playwright CI worker count, retries, and focused-test guard. Publish `output/playwright/` as artifacts and choose the retention period in your CI configuration.

Use `pnpm test` to run unit and browser suites together. Run builds and backend tests separately.

## Maintain fixtures and contracts

Keep [tests/fixtures/](../tests/fixtures/) aligned with frontend domain types and backend projections. When changing a rule or metric, update both implementations and verify parity. To export updated sample definitions:

```powershell
node --import ./scripts/register.mjs scripts/export-demo-manifest.mjs
Copy-Item output/backend-integration/demo-datasets.json ../datagaurd.back-end/config/demo-datasets.json
```

Keep the exporter invocation above so `scripts/register.mjs` resolves application imports; let Vitest resolve test imports. Review the exported small-sample rows and rules, and keep the large-customer generator specification aligned across both projects. Use fresh storage to verify manifest changes because updating the manifest does not overwrite existing backend versions.
