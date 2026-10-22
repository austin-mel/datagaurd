import { createSeededDatasets, getSeededDatasetRows, seededRuleCatalog } from '@/data'
import type { Dataset } from '@/types'
import { cloneRuleset, rulesetSignature } from '@/utils'
import { assertValidRuleset } from './rulesetValidation'
import { createDatasetCsv } from './datasetCsv'
import type { DatasetRepository } from './datasetRepositoryContract'
import { hasPendingValidation } from './validationState'
import { downloadFilename, historyEvent, nextVersion, validationSignature, type SourceRow, type SessionData } from './seededSession'
import { validateSeededDataset } from './seededValidation'
import { applySeededCellReview } from './seededCellReview'

export function createSeededDatasetRepository(): DatasetRepository {
  let records: Dataset[] | undefined
  const versions = new Map<string, Dataset>()
  const versionRows = new Map<string, readonly SourceRow[]>()
  const parents = new Map<string, string>()
  const sessions = new Map<string, SessionData>()
  const appliedRules = new Map<string, string>()
  function snapshot(record: Dataset, data: SessionData) {
    versions.set(record.id + ':' + record.version, structuredClone(record))
    // Rows are immutable: replacements allocate new objects and deletions a new array.
    versionRows.set(record.id + ':' + record.version, data.rows)
  }
  function getRecords() {
    records ??= createSeededDatasets().map(record => {
      const data: SessionData = { rows: [...getSeededDatasetRows(record.id)].map((values, index) => ({ id: index + 1, values })), ignored: new Set() }
      sessions.set(record.id, data)
      const dataset = { ...record, ...validateSeededDataset(record, data, new Date(record.lastValidatedAt ?? Date.now())) }
      appliedRules.set(record.id, validationSignature(record.ruleset))
      snapshot(dataset, data)
      return dataset
    })
    return records
  }
  function find(datasetId: string) {
    const record = getRecords().find(dataset => dataset.id === datasetId)
    const data = sessions.get(datasetId)
    if (!record || !data) throw new Error('Dataset not found')
    return { record, data }
  }
  function assertCurrent(record: Dataset, version: string) {
    if (record.version !== version) throw new Error('A newer version is available. Refresh before saving changes.')
    if (record.processingStatus === 'running') throw new Error('Wait for validation to finish before saving changes.')
  }
  function commit(updated: Dataset, data: SessionData) {
    sessions.set(updated.id, data)
    records = getRecords().map(record => record.id === updated.id ? updated : record)
    snapshot(updated, data)
    return structuredClone(updated)
  }
  return {
    source: { kind: 'seeded', reason: 'not-configured' },
    async getWorkspace() { return structuredClone({ datasets: getRecords(), ruleCatalog: seededRuleCatalog }) },
    async getDataset(datasetId) { return structuredClone(find(datasetId).record) },
    async download(datasetId, version) {
      getRecords()
      const record = versions.get(datasetId + ':' + version), rows = versionRows.get(datasetId + ':' + version)
      if (!record || !rows) throw new Error('Dataset version not found')
      return {
        filename: record.downloadFilename ?? downloadFilename(record, record.version),
        blob: createDatasetCsv(record.columns, rows.map(row => row.values)),
      }
    },
    async updateRuleset(datasetId, ruleset) {
      const { record } = find(datasetId)
      assertCurrent(record, record.version)
      if (ruleset.kind !== 'custom') throw new Error('Create a custom ruleset before saving changes.')
      ruleset = { ...ruleset, backendConfiguration: record.ruleset.backendConfiguration }
      assertValidRuleset(ruleset, record.columns)
      const signature = rulesetSignature(ruleset)
      if (signature === rulesetSignature(record.ruleset)) return structuredClone(record)
      const changed = validationSignature(ruleset) !== appliedRules.get(record.id)
      Object.assign(record, {
        ruleset: cloneRuleset(ruleset), rulesChangedSinceRun: changed,
        validationPending: changed || !!record.reviewChangedSinceRun || !!record.dataChangedSinceRun || record.processingStatus !== 'completed',
        history: [...(record.history ?? []), historyEvent('Ruleset saved', `${ruleset.name} · ${ruleset.rules.length} rule(s) saved.`)],
      })
      return structuredClone(record)
    },
    async revalidate(datasetId, sourceVersion) {
      const { record, data } = find(datasetId)
      assertCurrent(record, sourceVersion)
      if (!hasPendingValidation(record)) return structuredClone(record)
      // A pending edited version already has its own immutable source snapshot.
      const reuseVersion = !!record.dataChangedSinceRun || record.processingStatus === 'failed' || record.processingStatus === 'not_started'
      const version = reuseVersion ? record.version : nextVersion(record)
      const currentKey = record.id + ':' + record.version
      const parentKey = reuseVersion ? parents.get(currentKey) : currentKey
      const baselineRecord = parentKey ? versions.get(parentKey) : undefined
      const baselineRows = parentKey ? versionRows.get(parentKey) : undefined
      const baseline = baselineRecord && baselineRows ? { rows: baselineRows.map(row => row.values), columns: baselineRecord.columns, version: baselineRecord.version } : undefined
      const report = validateSeededDataset(record, data, new Date(), baseline)
      if (!reuseVersion) parents.set(record.id + ':' + version, currentKey)
      const updated: Dataset = { ...record, ...report, version,
        versionId: reuseVersion ? record.versionId : crypto.randomUUID(), latestRunId: crypto.randomUUID(),
        downloadFilename: downloadFilename(record, version), processingError: undefined,
        reviewChangedSinceRun: false, dataChangedSinceRun: false,
        history: [...(record.history ?? []), historyEvent('Validation ran', version + ' · Validation results saved.')],
      }
      appliedRules.set(datasetId, validationSignature(record.ruleset))
      return commit(updated, data)
    },
    async applyCellReview(datasetId, request) {
      const { record, data } = find(datasetId)
      assertCurrent(record, request.version)
      const updated = applySeededCellReview(record, data, request)
      if (updated.record.version !== record.version) parents.set(record.id + ':' + updated.record.version, record.id + ':' + record.version)
      return commit(updated.record, updated.data)
    },
  }
}
