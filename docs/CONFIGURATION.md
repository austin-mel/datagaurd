# Frontend Configuration and Troubleshooting

[README](../README.md) · [Architecture](ARCHITECTURE.md)

Configure your workspace data source, local API connection, and application path.

## Table of Contents

- [Environment files](#environment-files)
- [API connection](#api-connection)
- [Troubleshooting](#troubleshooting)

## Environment files

Configure local values in `environment/.front-end.env`. [vite.config.ts](../vite.config.ts) reads this file with Node's dotenv parser and gives process environment variables precedence. The configuration also sets `envDir: './environment/'`, so Vite loads standard `.env`, `.env.local`, `.env.[mode]`, and `.env.[mode].local` files from that directory. Use `.front-end.env` for the project's explicit overrides; its `VITE_` entries are injected through `define`, with shell values taking precedence.

Keep your settings in **environment/.front-end.env**, which the `environment/*.env` Git rule excludes from version control. Use this file for development and builds, or override values in your shell. The configuration injects only `VITE_` values into the browser bundle.

| Variable | Default | Meaning |
| --- | --- | --- |
| `VITE_API_BASE_URL` | `/api/v1` | Browser API base URL; include the workspace prefix |
| `VITE_DATA_SOURCE` | API unless exactly `seeded` | Explicit sample mode or initial API selection with availability fallback |
| `BACKEND_PROXY_TARGET` | `http://127.0.0.1:8000` | Vite development proxy destination; use the server origin, not `/api/v1` |
| `API_URL` | `http://127.0.0.1:8000/api/v1` | Node environment override for the opt-in live parity test only |

Treat every `VITE_` variable as public build-time data. Keep passwords and secrets out of these variables. Restart Vite after edits; rebuild your bundle to change its embedded API settings.

Select sample mode for your PowerShell session:

```powershell
$env:VITE_DATA_SOURCE = 'seeded'
pnpm dev
# After stopping Vite:
Remove-Item Env:VITE_DATA_SOURCE
```

## API connection

Same-origin development uses the built-in `/api` proxy. For a separate API origin, set an absolute base such as `http://127.0.0.1:8000/api/v1` and configure the backend's `DATAGUARD_CORS_ORIGINS` with a JSON array of frontend origins. Defaults permit `http://127.0.0.1:5173` and `http://localhost:5173`. A different port is a different origin.

The client has no login or token flow, and CORS does not authenticate requests. Use the [failure matrix](ARCHITECTURE.md#source-selection-and-failures) to understand how response headers and status codes affect fallback.

## Troubleshooting

| Symptom | Check and resolution |
| --- | --- |
| Environment edits do nothing | Use `environment/.front-end.env`; check process overrides; restart Vite or rebuild |
| Direct page links or refresh return 404 on GitHub Pages | Build and deploy the complete `dist` directory, including `404.html`, under `/dataguard/`. The fallback restores the requested route before Vue Router starts |
| Sample banner when you expect live data | Check `/health`, proxy target, network tab, and backend logs; reconnect reloads and loses sample edits |
| Live banner with no datasets | Fresh storage is empty; upload a file or explicitly seed demos |
| Connection error remains visible | 401/403/422, JSON 500, and malformed contracts intentionally do not trigger fallback. A workspace endpoint 404 on initial load selects samples; dataset 404 errors remain visible |
| CORS error with an absolute API URL | Permit the exact frontend scheme, hostname, and port on the backend |
| Vite cannot bind | Development requires port 5173; browser tests require port 4173; both use strict ports |
| Upload disabled | Samples cannot upload; live mode also requires a successfully loaded upload policy |
| Excel upload asks for a sheet | Supply the exact worksheet name for a workbook containing multiple sheets |
| Rules saved but score unchanged | Click Run Dataset Validation; saving does not perform the check |
| Validation button disabled | No pending changes, another operation is active, or validation is already running |
| Edit gets stale-version/finding conflict | Refresh and reselect the finding; do not reuse an old group or row position |
| Scores show unavailable | No completed run, zero denominator, missing required structure, or no uniqueness rule |
| Live parity test fails after editing samples | Seed reruns preserve edits; use isolated fresh backend storage for parity |
| Large dataset feels slow | Full workspace projection and in-browser sample computation are currently eager |
