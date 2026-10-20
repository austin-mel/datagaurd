import { writeFileSync, mkdirSync } from 'node:fs'
import { createSeededDatasets, getSeededDatasetRows, seededDatasetIds } from '../src/data/index.ts'
import { rulesToBackend } from '../src/services/index.ts'

// Export the frontend's actual rules and small fixture rows for the backend seed command.
const datasets = createSeededDatasets().map(dataset => ({
  id: dataset.id, name: dataset.name, filename: dataset.filename, columns: dataset.columns, row_count: dataset.rowCount,
  rules: dataset.ruleset.kind === 'default' ? dataset.ruleset.backendConfiguration
    : rulesToBackend(dataset.ruleset, dataset.columns),
  ...(dataset.id !== seededDatasetIds.customers ? { rows: [...getSeededDatasetRows(dataset.id)] } : { generator: 'customers-v1' }),
}))
mkdirSync('output/backend-integration', { recursive: true })
writeFileSync('output/backend-integration/demo-datasets.json', JSON.stringify(datasets, null, 2) + '\n')
