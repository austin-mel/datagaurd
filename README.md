# datagaurd.front-end

Dataguard's Vue 3 workspace for dataset profiling and quality rules.

## Dataset data flow

All dataset and ruleset records are seeded. `src/data/datasets.ts` contains dataset metadata, column profiles, history, and each assigned ruleset's ID, name, description, kind, and rules. `src/data/qualityRules.ts` contains the rule editor catalog: available types, display labels, date conditions, and defaults for newly added rules. Fictional source rows in `src/data/datasetRows.ts` supply local validation and CSV downloads. Static interface labels and styling remain in the components.

`src/services/seededDatasetRepository.ts` asynchronously returns a complete `DatasetWorkspace` containing datasets and the rule editor catalog. It clones seed records so session edits cannot mutate the original fixtures. The shared Pinia store in `src/stores/datasets.ts` loads this workspace once and passes its data to both views and their components. Components do not import seed records or hardcode dataset-specific values or rule defaults.

Domain types live in `src/types`, independently of seed implementations. `src/utils/rulesets.ts` creates rules from the fetched catalog and clones rulesets without discarding their metadata.

The recent-datasets Pinia store persists only the three most recently opened dataset IDs and timestamps in `localStorage`, under `dataguard.recentDatasets.v1`. Overview defaults to the latest available dataset in that history, or the first dataset when there is no history. An explicit dataset selection becomes the latest entry. Names, metadata, and report contents are always resolved from the dataset store.

Rule changes currently live in the seeded repository for the running app session. Saving revalidates that dataset and updates its issues, affected-row counts, quality scores, status, and validation timestamp together. Both pages use those shared results. Initial reports use the seed's validation date; subsequent saves use the current date in Pacific time. Required checks count missing values, while other checks skip them. Unique checks count every row sharing a duplicate non-empty value. Every dataset retains an assigned default or custom ruleset. If that ruleset has no enabled checks, its assignment remains visible while scores are unavailable and the report is marked not evaluated.

## Future backend integration

There is no API implementation, endpoint configuration, or network request code. The `backendRepository` variable in `src/services/datasetRepository.ts` is intentionally `undefined` and is the placeholder for future development.

When a backend is developed, supply an implementation of `DatasetRepository` from `src/services/datasetRepositoryContract.ts` at that placeholder. Views and components can keep their existing store bindings. The contract is:

| Member | Result |
| --- | --- |
| `source` | `{ kind: 'api' }` for a future live adapter |
| `getWorkspace()` | `Promise<DatasetWorkspace>` with complete dataset records and the rule editor catalog |
| `updateRuleset(datasetId, ruleset)` | `Promise<Dataset>` with the saved ruleset and refreshed validation results, scores, and history |
| `download(datasetId, version)` | `Promise<{ filename: string; blob: Blob }>` for the requested CSV version |

The future adapter should validate external responses against these domain types and translate connection failures into `BackendUnavailableError`. Transport, authentication, response parsing, and endpoints are intentionally left for that future implementation.

`createDatasetRepository()` provides the source selection and fallback mechanism. With no backend it uses seeds immediately. If a future backend reports `BackendUnavailableError` while loading a workspace, it returns the entire seeded workspace and marks its source as a fallback. An empty successful live workspace remains empty; other errors propagate. The UI identifies sample data and explains that its edits stay in the current session.

After falling back, reads, ruleset edits, and downloads continue using that seeded session until the application reloads. Failed live saves or downloads are never replayed against sample records, and sample edits are never synced to a future backend. This prevents a local edit from appearing to be a successful live save.

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Type Support for `.vue` Imports in TS

TypeScript cannot handle type information for `.vue` imports by default, so we replace the `tsc` CLI with `vue-tsc` for type checking. In editors, we need [Volar](https://marketplace.visualstudio.com/items?itemName=Vue.volar) to make the TypeScript language service aware of `.vue` types.

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
pnpm install
```

### Compile and Hot-Reload for Development

```sh
pnpm dev
```

### Type-Check, Compile and Minify for Production

```sh
pnpm build
```
