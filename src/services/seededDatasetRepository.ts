import { createSeededDatasets, getSeededDatasetRows, seededRuleCatalog } from '@/data'
import type { CellReviewGroup, CellReviewRequest, Dataset, DatasetHistoryEvent, DatasetRow, DatasetRuleset } from '@/types'
import { cloneRuleset, rulesetSignature } from '@/utils'
import { assertValidRuleset, validateDataset } from './datasetValidation'
import { createDatasetCsv } from './datasetCsv'
import type { DatasetRepository } from './datasetRepositoryContract'
import { countStatisticalWarnings } from './statisticalWarnings'
import { groupCellFinding } from './cellReview'
import { analyzeSeededStatistics, type StatisticalBaseline } from './seededStatistics'
import { resolveIdentifier } from './identifiers'
import { hasPendingValidation } from './validationState'

type SourceRow = { id: number; values: DatasetRow }
type SessionData = { rows: readonly SourceRow[]; ignored: ReadonlySet<string> }

// Default/custom is editor metadata, not a change to validation or ignore semantics.
function validationSignature(ruleset: DatasetRuleset) {
  return rulesetSignature({ ...ruleset, kind: 'custom' })
}
function ruleSignatures(ruleset: DatasetRuleset) {
  return new Map(ruleset.rules.map(rule => [rule.id, validationSignature({ ...ruleset, rules: [rule] })]))
}
function ignoreKey(row: SourceRow, column: string, kind: CellReviewGroup['kind'], ruleId: string, signature?: string) {
  return JSON.stringify([row.id, column, kind, ruleId, row.values[column] ?? null, signature ?? null])
}

function validateSeededDataset(record: Pick<Dataset, 'id' | 'columns' | 'ruleset'>, data: SessionData, validatedAt: Date, baseline?: StatisticalBaseline) {
  const rows = data.rows.map(row => row.values), signatures = ruleSignatures(record.ruleset)
  const report = validateDataset(rows, record.columns, record.ruleset, validatedAt, (index, rule) => {
    if (!data.ignored.size) return false
    const row = data.rows[index]
    return !!row && data.ignored.has(ignoreKey(row, rule.column, 'violation', rule.id, signatures.get(rule.id)))
  })
  const findings = analyzeSeededStatistics(rows, record.columns, record.ruleset, report.columnProfiles ?? [], baseline).flatMap(finding => {
    if (finding.column === null || !finding.affected_record_numbers.length) return [finding]
    const column = finding.column
    const members = finding.affected_record_numbers.filter(number => {
      const row = data.rows[number - 1]
      return row && !data.ignored.has(ignoreKey(row, column, 'warning', finding.rule_id))
    })
    return members.length ? [{ ...finding, affected_count: members.length, affected_record_numbers: members,
      record_samples: finding.record_samples.filter(sample => members.includes(sample.record_number)) }] : []
  })
  const identifierColumn = resolveIdentifier(record.ruleset, record.columns).column ?? undefined
  report.cellReview = [...(report.cellReview ?? []), ...findings.flatMap(finding => finding.column === null ? [] :
    groupCellFinding({ column: finding.column, ruleId: finding.rule_id, rule: finding.rule_id,
      kind: 'warning', reason: finding.explanation }, rows, finding.affected_record_numbers, identifierColumn))]
  report.columnProfiles = report.columnProfiles?.map(profile => ({
    ...profile, warningCount: countStatisticalWarnings(profile.name, findings),
  })) ?? null
  if (findings.length) report.status = 'needs-review'
  const globalWarnings = findings.filter(finding => !finding.affected_record_numbers.length)
  if (globalWarnings.length) report.qualityNote += ' Dataset warnings: ' + [...new Set(globalWarnings.map(finding => finding.explanation))].join(' ')
  if (data.ignored.size) report.qualityNote += ' Ignored rule findings are excluded from error counts; completeness still reflects actual missing cells.'
  return report
}

function nextVersion(record: Dataset) { return 'v' + (Number(record.version.replace(/^v/, '')) + 1) }
function downloadFilename(record: Dataset, version: string) {
  return (record.filename ?? record.name).replace(/\.[^.]+$/, '') + '_' + version + '.csv'
}
function historyEvent(title: DatasetHistoryEvent['title'], description: string): DatasetHistoryEvent {
  return { id: crypto.randomUUID(), occurredAt: new Date().toISOString(), title, description }
}

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
    async applyCellReview(datasetId: string, request: CellReviewRequest) {
      const { record, data } = find(datasetId)
      assertCurrent(record, request.version)
      const group = record.cellReview?.find(item => item.id === request.groupId)
      if (!group || !group.cells.some(cell => cell.rowNumber === request.rowNumber)) throw new Error('This finding is no longer available. Refresh the review.')
      const cells = request.scope === 'all' ? group.cells : group.cells.filter(cell => cell.rowNumber === request.rowNumber)
      const rowNumbers = new Set(cells.map(cell => cell.rowNumber))
      const action = request.action
      if (action.type === 'ignore') {
        const ignored = new Set(data.ignored), signatures = ruleSignatures(record.ruleset)
        for (const cell of cells) {
          const row = data.rows[cell.rowNumber - 1]
          if (!row) throw new Error('The selected row is no longer available.')
          ignored.add(ignoreKey(row, group.column, group.kind, group.ruleId, group.kind === 'violation' ? signatures.get(group.ruleId) : undefined))
        }
        const cellReview = (record.cellReview ?? []).flatMap(item => {
          const remaining = item.id === group.id ? item.cells.filter(cell => !rowNumbers.has(cell.rowNumber)) : item.cells
          return remaining.length ? [{ ...item, cells: remaining }] : []
        })
        if (action.reason.length > 2000) throw new Error('Ignore reasons must be at most 2000 characters.')
        return commit({ ...record, cellReview, reviewChangedSinceRun: true, validationPending: true,
          history: [...(record.history ?? []), historyEvent('Findings ignored', `${record.version} · ${cells.length} finding(s) · ${group.column} · ${group.rule}${action.reason.trim() ? ' · ' + action.reason.trim() : ''}`)],
        }, { ...data, ignored })
      }
      if (action.type === 'replace') {
        if (action.value !== null && !action.value.trim()) throw new Error('Enter a replacement value, or choose Replace with NULL.')
        if (action.value?.includes('\0')) throw new Error('Replacement values cannot contain NUL characters.')
        if (action.value === group.currentValue || (action.value !== null && group.currentValue !== null && action.value === String(group.currentValue))) throw new Error('Enter a value different from the current value.')
        if (request.scope === 'all' && cells.length > 1 && record.ruleset.rules.some(rule => rule.enabled && rule.type === 'unique' && rule.column === group.column)) throw new Error('Replace unique values one cell at a time.')
      }
      const rows = data.rows.flatMap((row, index) => {
        if (!rowNumbers.has(index + 1)) return [row]
        return action.type === 'delete-row' ? [] : [{ ...row, values: { ...row.values, [group.column]: action.value } }]
      })
      const newPositions = new Map(rows.map((row, index) => [row.id, index + 1]))
      const identifierColumn = resolveIdentifier(record.ruleset, record.columns).column ?? undefined
      // Keep the remaining last-run queue usable without running validation.
      // Edited cells leave this queue; any new failures appear on the next run.
      const cellReview = (record.cellReview ?? []).flatMap(item => {
        const remaining = item.cells.flatMap(cell => {
          if (rowNumbers.has(cell.rowNumber) && (action.type === 'delete-row' || item.column === group.column)) return []
          const oldRow = data.rows[cell.rowNumber - 1]
          const position = oldRow && newPositions.get(oldRow.id)
          if (!position) return []
          const identifier = identifierColumn ? rows[position - 1]?.values[identifierColumn] : null
          return [{ rowNumber: position, identifier: identifier == null || identifier === '' ? null : String(identifier) }]
        })
        return remaining.length ? [{ ...item, cells: remaining }] : []
      })
      const version = nextVersion(record)
      parents.set(record.id + ':' + version, record.id + ':' + record.version)
      const updated: Dataset = { ...record, version, versionId: crypto.randomUUID(), latestRunId: undefined,
        rowCount: rows.length, downloadFilename: downloadFilename(record, version), cellReview,
        reviewChangedSinceRun: true, dataChangedSinceRun: true, validationPending: true,
        processingStatus: 'not_started', status: 'unvalidated', processingError: undefined,
        validation: null, columnProfiles: null, quality: null, lastValidatedAt: null,
        qualityDimensions: record.qualityDimensions.map(dimension => ({ ...dimension, score: null, passed: null, total: null })),
        qualityNote: 'Data changed. Run validation to calculate profiles, issues, and quality scores.',
        history: [...(record.history ?? []), historyEvent('Dataset edited', `${version} · ${cells.length} ${action.type === 'delete-row' ? 'row(s) deleted' : 'cell(s) updated in ' + group.column}`)],
      }
      return commit(updated, { ...data, rows })
    },
  }
}
