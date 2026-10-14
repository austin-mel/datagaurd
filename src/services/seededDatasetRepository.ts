import { createSeededDatasets, getSeededDatasetRows, seededRuleCatalog } from '@/data'
import type { Dataset } from '@/types'
import { cloneRuleset, rulesetSignature } from '@/utils'
import { assertValidRuleset, validateDataset } from './datasetValidation'
import { createDatasetCsv } from './datasetCsv'
import type { DatasetRepository } from './datasetRepositoryContract'

export function createSeededDatasetRepository(): DatasetRepository {
  let records: Dataset[] | undefined
  const versions = new Map<string, Dataset>()
  function getRecords() {
    records ??= createSeededDatasets().map(record => {
      const dataset = { ...record, ...validateDataset(getSeededDatasetRows(record.id), record.columns, record.ruleset, new Date(record.lastValidatedAt ?? Date.now())) }
      versions.set(dataset.id + ':' + dataset.version, structuredClone(dataset))
      return dataset
    })
    return records
  }
  function find(datasetId: string) {
    const record = getRecords().find(dataset => dataset.id === datasetId)
    if (!record) throw new Error('Dataset not found')
    return record
  }
  return {
    source: { kind: 'seeded', reason: 'not-configured' },
    async getWorkspace() {
      return structuredClone({ datasets: getRecords(), ruleCatalog: seededRuleCatalog })
    },
    async getDataset(datasetId) { return structuredClone(find(datasetId)) },
    async download(datasetId, version) {
      getRecords()
      const record = versions.get(datasetId + ':' + version)
      if (!record) throw new Error('Dataset version not found')
      return {
        filename: record.downloadFilename ?? record.id + '_' + record.version + '.csv',
        blob: createDatasetCsv(record.columns, getSeededDatasetRows(record.id)),
      }
    },
    async updateRuleset(datasetId, ruleset) {
      const record = find(datasetId)
      assertValidRuleset(ruleset, record.columns)
      const signature = rulesetSignature(ruleset)
      if (signature === rulesetSignature(record.ruleset)) return structuredClone(record)
      const lastRun = versions.get(record.id + ':' + record.version)
      Object.assign(record, {
        ruleset: cloneRuleset(ruleset), rulesChangedSinceRun: !lastRun || signature !== rulesetSignature(lastRun.ruleset),
      })
      return structuredClone(record)
    },
    async revalidate(datasetId, sourceVersion) {
      const record = find(datasetId)
      if (record.version !== sourceVersion) throw new Error('A newer version is available. Refresh before revalidating.')
      if (!record.rulesChangedSinceRun) return structuredClone(record)
      const version = 'v' + (Number(sourceVersion.replace(/^v/, '')) + 1)
      const startedAt = new Date().toISOString()
      Object.assign(record, {
        version, versionId: crypto.randomUUID(), latestRunId: crypto.randomUUID(),
        downloadFilename: datasetId + '_' + version + '.csv',
        processingStatus: 'running', status: 'running', lastValidatedAt: null, validation: null, columnProfiles: null,
        quality: null, qualityDimensions: record.qualityDimensions.map(dimension => ({ ...dimension, score: null, passed: null, total: null })),
        history: [...(record.history ?? []), {
          id: crypto.randomUUID(), occurredAt: startedAt,
          title: 'Validation started for ' + version, description: 'New version created from ' + sourceVersion + '.',
        }],
      })
      try {
        const report = validateDataset(getSeededDatasetRows(record.id), record.columns, record.ruleset, new Date())
        Object.assign(record, report, { processingError: undefined })
        record.history = [...(record.history ?? []), {
          id: crypto.randomUUID(), occurredAt: report.lastValidatedAt ?? startedAt,
          title: 'Dataset validation completed', description: version + ' · Profiles, issues, and quality scores recalculated.',
        }]
      } catch (cause) {
        Object.assign(record, {
          processingStatus: 'failed', status: 'failed', processingError: cause instanceof Error ? cause.message : 'Validation failed.',
          qualityNote: 'Validation failed. Results are not available.',
        })
        record.history = [...(record.history ?? []), {
          id: crypto.randomUUID(), occurredAt: new Date().toISOString(),
          title: 'Dataset validation failed', description: version + ' · Results are not available. Retry validation.',
        }]
      }
      versions.set(datasetId + ':' + version, structuredClone(record))
      return structuredClone(record)
    },
  }
}

