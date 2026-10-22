import type { CellReviewRequest, Dataset } from '@/types'
import { resolveIdentifier } from './identifiers'
import { clearValidationResults } from './validationState'
import { downloadFilename, historyEvent, ignoreKey, nextVersion, ruleSignatures, type SessionData } from './seededSession'

export function applySeededCellReview(record: Dataset, data: SessionData, request: CellReviewRequest): { record: Dataset; data: SessionData } {
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
    return { record: { ...record, cellReview, reviewChangedSinceRun: true, validationPending: true,
      history: [...(record.history ?? []), historyEvent('Findings ignored', `${record.version} · ${cells.length} finding(s) · ${group.column} · ${group.rule}${action.reason.trim() ? ' · ' + action.reason.trim() : ''}`)],
    }, data: { ...data, ignored } }
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
  const updated: Dataset = { ...clearValidationResults(record), version, versionId: crypto.randomUUID(), latestRunId: undefined,
    rowCount: rows.length, downloadFilename: downloadFilename(record, version), cellReview,
    reviewChangedSinceRun: true, dataChangedSinceRun: true, validationPending: true,
    processingStatus: 'not_started', status: 'unvalidated', processingError: undefined,
    qualityNote: 'Data changed. Run validation to calculate profiles, issues, and quality scores.',
    history: [...(record.history ?? []), historyEvent('Dataset edited', `${version} · ${cells.length} ${action.type === 'delete-row' ? 'row(s) deleted' : 'cell(s) updated in ' + group.column}`)],
  }
  return { record: updated, data: { ...data, rows } }
}
