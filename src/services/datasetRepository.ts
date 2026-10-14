import { createSeededDatasets, cloneRuleset, getSeededDatasetRows, type DatasetRuleset } from '@/data'
import type { Dataset } from '@/types'
import { formatNumber, formatScore } from '@/utils'
import { validateDataset } from './datasetValidation'
import { createDatasetCsv } from './datasetCsv'

// Implement this interface with API calls when the backend is available.
export interface DatasetRepository {
  list(): Promise<Dataset[]>
  download(datasetId: string, version: string): Promise<{ filename: string; blob: Blob }>
  updateRuleset(datasetId: string, ruleset: DatasetRuleset): Promise<Dataset>
}

export function createSeededDatasetRepository(): DatasetRepository {
  let records: Dataset[] | undefined
  function getRecords() {
    records ??= createSeededDatasets().map(record => ({
      ...record,
      ...validateDataset(getSeededDatasetRows(record.id), record.columns, record.ruleset, new Date(record.lastValidatedAt)),
    }))
    return records
  }
  return {
    async list() {
      return structuredClone(getRecords())
    },
    async download(datasetId, version) {
      const record = getRecords().find(dataset => dataset.id === datasetId && dataset.version === version)
      if (!record) throw new Error('Dataset version not found')
      return {
        filename: record.downloadFilename ?? `${record.id}_${record.version}.csv`,
        blob: createDatasetCsv(record.columns, getSeededDatasetRows(record.id)),
      }
    },
    async updateRuleset(datasetId, ruleset) {
      const record = getRecords().find(dataset => dataset.id === datasetId)
      if (!record) throw new Error('Dataset not found')
      const savedRuleset = cloneRuleset(ruleset)
      const report = validateDataset(getSeededDatasetRows(record.id), record.columns, savedRuleset, new Date())
      const issueCount = report.validation.issues.length
      const history = [...(record.history ?? []), {
        id: crypto.randomUUID(),
        occurredAt: report.lastValidatedAt,
        title: 'Quality rules updated and validation completed',
        description: `System · ${formatNumber(issueCount)} ${issueCount === 1 ? 'issue' : 'issues'} · ${report.quality === null ? 'No quality score available' : `Overall quality ${formatScore(report.quality)} / 100`}`,
      }]
      // Commit the rules and their results together only after validation succeeds.
      Object.assign(record, report, { ruleset: savedRuleset, history })
      return structuredClone(record)
    },
  }
}

export const datasetRepository: DatasetRepository = createSeededDatasetRepository()
