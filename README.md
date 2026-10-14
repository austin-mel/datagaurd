# datagaurd.front-end

Dataguard's Vue 3 workspace for dataset profiling and quality rules.

## Dataset data flow

Dataset metadata, column profiles, and rules originate in `src/data/datasets.ts`. Fictional source rows in `src/data/datasetRows.ts` supply the local validator, which derives issues and quality scores from enabled rules. The asynchronous `DatasetRepository` interface in `src/services/datasetRepository.ts` supplies the shared Pinia dataset store. To connect a backend, replace the exported repository with an API implementation returning the types in `src/types`; the views and report components consume the same store and need no seed-specific changes.

The recent-datasets Pinia store persists only the three most recently opened dataset IDs and timestamps in `localStorage`, under `dataguard.recentDatasets.v1`. Overview defaults to the latest available dataset in that history, or the first dataset when there is no history. An explicit dataset selection becomes the latest entry. Names, metadata, and report contents are always resolved from the dataset store.

Rule changes currently live in the seeded repository for the running app session. Saving revalidates that dataset and updates its issues, affected-row counts, quality scores, status, and validation timestamp together. Both pages use those shared results. Initial reports use the seed's validation date; subsequent saves use the current date in Pacific time. Required checks count missing values, while other checks skip them. Unique checks count every row sharing a duplicate non-empty value. Every dataset retains an assigned default or custom ruleset. If that ruleset has no enabled checks, its assignment remains visible while scores are unavailable and the report is marked not evaluated.

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
