import { writeFileSync, mkdirSync } from 'node:fs'
import { createSeededDatasets } from '../src/data/datasets.ts'
import { getSeededDatasetRows } from '../src/data/datasetRows.ts'
import { rulesToBackend } from '../src/services/ruleExport.ts'
import { seededDatasetIds } from '../src/data/datasetIds.ts'

// Export the frontend's actual rules and small fixture rows for the backend seed command.
const datasets = createSeededDatasets().map(dataset => ({
  id: dataset.id, name: dataset.name, filename: dataset.filename, columns: dataset.columns, row_count: dataset.rowCount,
  rules: dataset.ruleset.kind === 'default' ? dataset.ruleset.backendConfiguration
    : rulesToBackend(dataset.ruleset, dataset.columns),
  ...(dataset.id !== seededDatasetIds.customers ? { rows: [...getSeededDatasetRows(dataset.id)] } : { generator: 'customers-v1' }),
}))
mkdirSync('output/backend-integration', { recursive: true })
writeFileSync('output/backend-integration/demo-datasets.json', JSON.stringify(datasets, null, 2) + '\n')
