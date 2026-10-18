# Frontend Configuration and Hosting

[README](../README.md) · [Architecture](ARCHITECTURE.md)

Configure your workspace data source, API connection, application path, and static hosting.

## Table of Contents

- [Environment files](#environment-files)
- [API connection](#api-connection)
- [Production hosting](#production-hosting)
- [Troubleshooting](#troubleshooting)

## Environment files

Configure local values in `environment/front-end.env`. [vite.config.ts](../vite.config.ts) reads this file with Node's dotenv parser and gives process environment variables precedence. The configuration also sets `envDir: './environment/'`, so Vite loads standard `.env`, `.env.local`, `.env.[mode]`, and `.env.[mode].local` files from that directory. Use `front-end.env` for the project's explicit overrides; its `VITE_` entries are injected through `define`, with shell values taking precedence.

Keep your settings in **environment/front-end.env**, which the `environment/*.env` Git rule excludes from version control. Use this file for development and builds, and supply process overrides for deployment-specific values. The configuration injects only `VITE_` values into the browser bundle.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api/v1` | Browser API base URL; include the workspace prefix |
| `VITE_DATA_SOURCE` | API unless exactly `seeded` | Explicit sample mode or initial API selection with availability fallback |
| `BACKEND_PROXY_TARGET` | `http://127.0.0.1:8000` | Vite development proxy destination; use the server origin, not `/api/v1` |
| `API_URL` | `http://127.0.0.1:8000/api/v1` | Node environment override for the opt-in live parity test only |

Treat every `VITE_` variable as public build-time data. Keep passwords and secrets out of these variables. Restart Vite after edits; rebuild your production bundle to change its embedded API settings.

Select sample mode for your PowerShell session:

```powershell
$env:VITE_DATA_SOURCE = 'seeded'
pnpm dev
# After stopping Vite:
Remove-Item Env:VITE_DATA_SOURCE
```

## API connection

Same-origin development uses the built-in `/api` proxy. For a separate API origin, set an absolute base such as `http://127.0.0.1:8000/api/v1` and configure the backend's `DATAGUARD_CORS_ORIGINS` with a JSON array of frontend origins. Defaults permit `http://127.0.0.1:5173` and `http://localhost:5173`. A different port is a different origin.

Plan authentication separately from CORS: the client has no login or token flow, and CORS does not authenticate requests. Use the [failure matrix](ARCHITECTURE.md#source-selection-and-failures) to understand how response headers and status codes affect fallback.

## Production hosting

1. Set the intended public build values and run `pnpm build`; deploy `dist/` under `/datagaurd/`, matching `base` in [vite.config.ts](../vite.config.ts). To host at another path, change `base` and rebuild.
2. Route `/api/*` to FastAPI without removing `/api/v1`, or build with an absolute API base URL.
3. Serve `/datagaurd/index.html` for frontend history routes such as `/datagaurd/datasets` and `/datagaurd/overview`. The router uses `import.meta.env.BASE_URL`; keep its fallback path aligned with your build base. Do not apply the HTML fallback to API requests.
4. Configure HTTPS and exact permitted frontend origins when the API is cross-origin.
5. Decide whether automatic sample fallback suits your deployment. To disable fallback while retaining API mode, change the repository-selection code; configuration provides no separate switch. Preserve the visible data-source banner.
6. Complete the backend's [production requirements](../../datagaurd.back-end/docs/OPERATIONS.md#production-readiness) before exposing sensitive or shared data.

Use `pnpm preview` to inspect your build locally, opening the printed server URL with `/datagaurd/` appended. Configure deployed API routing separately because static files do not include the Vite development proxy. If an API request returns HTML, correct the route; the client rejects HTML as a contract error.

## Troubleshooting

| Symptom | Check and resolution |
| --- | --- |
| Environment edits do nothing | Use `environment/front-end.env`; check process overrides; restart Vite or rebuild |
| Sample banner when you expect live data | Check `/health`, proxy target, network tab, and backend logs; reconnect reloads and loses sample edits |
| Live banner with no datasets | Fresh storage is empty; upload a file or explicitly seed demos |
| Connection error remains visible | 401/403/422, JSON 500, and malformed contracts intentionally do not trigger fallback. A workspace endpoint 404 on initial load selects samples; dataset 404 errors remain visible |
| CORS error with an absolute API URL | Permit the exact frontend scheme, hostname, and port on the backend |
| Vite cannot bind | Development requires port 5173; browser tests require port 4173; both use strict ports |
| Deep-link refresh returns 404 | Serve `/datagaurd/index.html` for frontend routes and retain the configured base path |
| Upload disabled | Samples cannot upload; live mode also requires a successfully loaded upload policy |
| Excel upload asks for a sheet | Supply the exact worksheet name for a workbook containing multiple sheets |
| Rules saved but score unchanged | Click Run Dataset Validation; saving does not perform the check |
| Validation button disabled | No pending changes, another operation is active, or validation is already running |
| Edit gets stale-version/finding conflict | Refresh and reselect the finding; do not reuse an old group or row position |
| Scores show unavailable | No completed run, zero denominator, missing required structure, or no uniqueness rule |
| Live parity test fails after editing samples | Seed reruns preserve edits; use isolated fresh backend storage for parity |
| Large dataset feels slow | Full workspace projection and in-browser sample computation are currently eager |
