import { writeFileSync, mkdirSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { pathToFileURL } from 'node:url'
import { createSeededDatasets, getSeededDatasetRows, seededDatasetIds } from '@/data'
import { rulesToBackend } from '@/services'

// Export the frontend's actual rules and small fixture rows for the backend seed command.
export function exportDemoManifest(outputPath = 'output/backend-integration/demo-datasets.json') {
  const datasets = createSeededDatasets().map(dataset => ({
    id: dataset.id, name: dataset.name, filename: dataset.filename, columns: dataset.columns, row_count: dataset.rowCount,
    rules: dataset.ruleset.kind === 'default' ? dataset.ruleset.backendConfiguration
      : rulesToBackend(dataset.ruleset, dataset.columns),
    ...(dataset.id !== seededDatasetIds.customers ? { rows: [...getSeededDatasetRows(dataset.id)] } : { generator: 'customers-v1' }),
  }))
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, JSON.stringify(datasets, null, 2) + '\n')
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  exportDemoManifest()
}
